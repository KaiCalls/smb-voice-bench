"""Synthetic SQLite business tools, durable requests and independent audit exports."""
from __future__ import annotations
import contextlib
import hmac
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from .canonical import canonical, digest, identifier, Invalid, parse, root_descriptor
from .contracts import validate

TOOLS = ('lookup_slots', 'create_booking', 'get_booking_status', 'record_confirmation')
MUTATIONS = ('create_booking', 'record_confirmation')

class Sandbox:
    def __init__(self, path):
        self.path = Path(path)
        with root_descriptor(self.path.parent):
            pass
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        self.lock = threading.RLock()
        with self.db() as db:
            db.executescript('''
            CREATE TABLE runs(id TEXT PRIMARY KEY, journey TEXT NOT NULL, scenario TEXT NOT NULL,
                capability_hash TEXT NOT NULL, closed INTEGER NOT NULL DEFAULT 0,
                revision INTEGER NOT NULL DEFAULT 0, clock INTEGER NOT NULL DEFAULT 0, current_slot TEXT);
            CREATE TABLE objects(kind TEXT NOT NULL, id TEXT PRIMARY KEY, run_id TEXT REFERENCES runs(id),
                parent TEXT, body TEXT NOT NULL, UNIQUE(run_id,kind,parent));
            CREATE TABLE permissions(seq INTEGER PRIMARY KEY, run_id TEXT REFERENCES runs(id), body TEXT NOT NULL);
            CREATE TABLE requests(seq INTEGER PRIMARY KEY, run_id TEXT REFERENCES runs(id),
                call_id TEXT NOT NULL, operation_id TEXT NOT NULL, body TEXT NOT NULL, at_ms INTEGER NOT NULL);
            CREATE TABLE outcomes(request_seq INTEGER PRIMARY KEY REFERENCES requests(seq), body TEXT NOT NULL, response TEXT NOT NULL);
            CREATE TABLE events(seq INTEGER PRIMARY KEY, run_id TEXT REFERENCES runs(id), body TEXT NOT NULL);
            CREATE TRIGGER requests_immutable_update BEFORE UPDATE ON requests BEGIN SELECT RAISE(ABORT,'immutable'); END;
            CREATE TRIGGER requests_immutable_delete BEFORE DELETE ON requests BEGIN SELECT RAISE(ABORT,'immutable'); END;
            CREATE TRIGGER outcomes_immutable_update BEFORE UPDATE ON outcomes BEGIN SELECT RAISE(ABORT,'immutable'); END;
            CREATE TRIGGER outcomes_immutable_delete BEFORE DELETE ON outcomes BEGIN SELECT RAISE(ABORT,'immutable'); END;
            CREATE TRIGGER events_immutable_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'immutable'); END;
            CREATE TRIGGER events_immutable_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'immutable'); END;
            ''')

    @contextlib.contextmanager
    def db(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @classmethod
    def open_existing(cls, path):
        # Recovery is audit-only: no capability is recovered or re-enabled.
        from .canonical import read_bytes, MAX_RUN
        path=Path(path)
        read_bytes(path.parent,path.name,MAX_RUN)
        instance=cls.__new__(cls);instance.path=path;instance.lock=threading.RLock()
        return instance

    def audit_run(self, run_id):
        identifier(run_id)
        with self.db() as db:
            if db.execute('SELECT 1 FROM runs WHERE id=?',(run_id,)).fetchone() is None:
                raise Invalid('unknown audit run')
        return AuditHandle(RunHandle(self,run_id,None))

    def create_run(self, run_id, journey_id, scenario):
        identifier(run_id); identifier(journey_id); validate(scenario, 'scenario')
        capability = secrets.token_hex(32)
        with self.db() as db:
            db.execute('INSERT INTO runs(id,journey,scenario,capability_hash) VALUES(?,?,?,?)',
                       (run_id, journey_id, canonical(scenario).decode(), digest(capability.encode())))
        return RunHandle(self, run_id, capability)

class RunHandle:
    def __init__(self, sandbox, run_id, capability):
        self._sandbox = sandbox
        self.run_id = run_id
        self.capability = capability

    def _run(self, db):
        return db.execute('SELECT * FROM runs WHERE id=?', (self.run_id,)).fetchone()

    def _event(self, db, kind, payload, operation=None, source='sandbox'):
        run = self._run(db)
        seq = db.execute('SELECT COUNT(*) FROM events WHERE run_id=?', (self.run_id,)).fetchone()[0] + 1
        event = dict(kind='event', schema_version='0.1.0', event_id='event_' + str(seq), run_id=self.run_id,
                     journey_id=run['journey'], sequence=seq, at_ms=run['clock'], type=kind,
                     source=source, operation_id=operation, payload=payload, extensions={})
        validate(event)
        db.execute('INSERT INTO events(run_id,body) VALUES(?,?)', (self.run_id, canonical(event).decode()))
        db.execute('UPDATE runs SET clock=clock+1 WHERE id=?', (self.run_id,))
        return event

    def emit(self, kind, payload, operation=None, source='harness'):
        with self._sandbox.lock, self._sandbox.db() as db:
            if self._run(db)['closed']:
                raise Invalid('closed harness')
            return self._event(db, kind, payload, operation, source)

    def record_permission(self, turn_id, slot_id, booking, confirmation):
        with self._sandbox.lock, self._sandbox.db() as db:
            run = self._run(db)
            scenario = parse(run['scenario'])
            events = [parse(x[0]) for x in db.execute('SELECT body FROM events WHERE run_id=?', (self.run_id,))]
            completed = [e['payload'] for e in events if e['type'] == 'caller.turn_completed']
            spec = dict(turn_id=turn_id, slot_id=slot_id, booking=booking, confirmation=confirmation)
            if run['closed'] or spec not in scenario['permissions'] or not completed or completed[-1]['turn_id'] != turn_id:
                raise Invalid('permission requires the current completed scripted turn')
            turn = next(t for t in scenario['caller_turns'] if t['turn_id'] == turn_id)
            if completed[-1]['text'] != turn['text']:
                raise Invalid('permission text mismatch')
            permission = dict(permission_id='permission_' + str(len(events)+1), run_id=self.run_id,
                              caller_turn_id=turn_id, slot_id=slot_id, booking=booking,
                              confirmation=confirmation, recorded_at_ms=run['clock'])
            validate(permission, 'permission')
            db.execute('INSERT INTO permissions(run_id,body) VALUES(?,?)', (self.run_id, canonical(permission).decode()))
            self._event(db, 'permission.recorded', {k: v for k, v in permission.items() if k not in ('run_id','recorded_at_ms')})

    def _objects(self, db, kind):
        return [parse(x[0]) for x in db.execute('SELECT body FROM objects WHERE run_id=? AND kind=? ORDER BY rowid', (self.run_id, kind))]

    def _put(self, db, kind, obj, parent):
        db.execute('INSERT INTO objects(kind,id,run_id,parent,body) VALUES(?,?,?,?,?)',
                   (kind, obj[kind + '_id'], self.run_id, parent, canonical(obj).decode()))

    def execute(self, capability, operation_id, request):
        validate(request, 'tool_request'); identifier(operation_id)
        with self._sandbox.lock:
            # First commit the requested operation. A process death leaves a durable pending audit.
            with self._sandbox.db() as db:
                run = self._run(db)
                seq = db.execute('INSERT INTO requests(run_id,call_id,operation_id,body,at_ms) VALUES(?,?,?,?,?)',
                     (self.run_id, request['call_id'], operation_id, canonical(request).decode(), run['clock'])).lastrowid
                self._event(db, 'tool.requested', request, operation_id)
            fault = parse(run['scenario'])['fault']
            authorized = not run['closed'] and isinstance(capability, str) and hmac.compare_digest(run['capability_hash'], digest(capability.encode()))
            if authorized and request['tool'] == 'lookup_slots' and fault['mode'] == 'slow_lookup':
                time.sleep(fault['delay_ms'] / 1000)  # no open write transaction
            with self._sandbox.db() as db:
                run = self._run(db)
                if authorized and request['tool'] == 'lookup_slots' and fault['mode'] == 'slow_lookup':
                    db.execute('UPDATE runs SET clock=clock+? WHERE id=?', (fault['delay_ms'], self.run_id))
                args = request['args']; tool = request['tool']; call_id = request['call_id']
                revision = run['revision']; disposition = 'accepted'; code = None
                response = {'status': 'failed', 'code': 'rejected'}
                previous = db.execute('SELECT r.*,o.response FROM requests r LEFT JOIN outcomes o ON o.request_seq=r.seq WHERE r.run_id=? AND r.seq<? ORDER BY r.seq', (self.run_id,seq)).fetchall()
                same_call = [p for p in previous if p['call_id'] == call_id or p['operation_id'] == operation_id]
                same_key = [p for p in previous if parse(p['body'])['tool'] == tool and args.get('idempotency_key') and parse(p['body'])['args'].get('idempotency_key') == args['idempotency_key']]
                chosen = same_call[-1:] or same_key[-1:]
                reservations = self._objects(db,'reservation'); bookings = self._objects(db,'booking')
                permissions = [parse(x[0]) for x in db.execute('SELECT body FROM permissions WHERE run_id=? ORDER BY seq', (self.run_id,))]
                permission = permissions[-1] if permissions else {}
                reservation = next((x for x in reservations if x['reservation_id'] == args.get('reservation_id')), None)
                booking = next((x for x in bookings if x['booking_id'] == args.get('booking_id')), None)
                if not authorized:
                    disposition, code = 'denied', 'invalid_or_closed_capability'
                elif len({p['call_id'] for p in previous}) >= 20 and not same_call:
                    disposition, code = 'denied', 'call_limit'
                elif chosen:
                    prior = chosen[0]; old = parse(prior['body'])
                    if old['tool'] != tool or old['args'] != args or (same_call and (old['call_id'] != call_id or prior['operation_id'] != operation_id)):
                        disposition, code = 'denied', 'identity_arguments_changed'
                    elif prior['response'] is None:
                        disposition, code = 'pending', 'unresolved_operation'
                    else:
                        disposition = 'deduplicated'; response = parse(prior['response'])
                elif tool == 'lookup_slots':
                    db.execute('UPDATE runs SET current_slot=? WHERE id=?',(args['slot_id'],self.run_id))
                    slot = next((s for s in parse(run['scenario'])['business_context']['slots'] if s['slot_id'] == args['slot_id']), None)
                    if not slot:
                        disposition, code = 'failed', 'unavailable_slot'
                    else:
                        obj = next((x for x in reservations if x['slot_id'] == slot['slot_id']), None)
                        if obj is None:
                            obj = dict(reservation_id='reservation_' + secrets.token_hex(8), run_id=self.run_id,
                                       operation_id=operation_id, **slot)
                            self._put(db,'reservation',obj,slot['slot_id'])
                        response = dict(status='available', **{k: obj[k] for k in ('reservation_id','slot_id','starts_at')})
                        code = 'slow_lookup' if fault['mode'] == 'slow_lookup' else None
                elif tool == 'get_booking_status':
                    found = next((b for b in bookings if b['reservation_id'] == args['reservation_id']), None)
                    response = dict(status='confirmed', booking_id=found['booking_id'], slot_id=found['slot_id']) if found else {'status':'not_found'}
                elif tool == 'create_booking':
                    if not reservation or not permission.get('booking') or permission.get('slot_id') != reservation['slot_id'] or run['current_slot'] != reservation['slot_id']:
                        disposition, code = 'denied', 'booking_not_authorized'
                    elif any(b['reservation_id'] == reservation['reservation_id'] for b in bookings):
                        disposition, code = 'denied', 'duplicate_booking_decision'
                    else:
                        revision += 1
                        obj = dict(booking_id='booking_' + secrets.token_hex(8), run_id=self.run_id,
                            reservation_id=reservation['reservation_id'], slot_id=reservation['slot_id'],
                            caller_name=args['caller_name'], service=args['service'], operation_id=operation_id, state_revision=revision)
                        self._put(db,'booking',obj,reservation['reservation_id'])
                        self._event(db,'booking.committed',{k:obj[k] for k in ('booking_id','reservation_id','slot_id','state_revision')},operation_id)
                        response = dict(status='confirmed',booking_id=obj['booking_id'],slot_id=obj['slot_id'])
                        if fault['mode'] == 'unknown_write':
                            disposition, code = 'response_unknown', 'unknown_write'
                            response = {'status':'unknown','code':'unknown_write'}
                elif tool == 'record_confirmation':
                    if not booking or not permission.get('confirmation') or permission.get('slot_id') != booking['slot_id']:
                        disposition, code = 'denied', 'confirmation_not_authorized'
                    elif self._objects(db,'confirmation'):
                        disposition, code = 'denied', 'duplicate_confirmation_decision'
                    else:
                        revision += 1
                        failed = fault['mode'] == 'message_failure'
                        obj = dict(confirmation_id='confirmation_' + secrets.token_hex(8),run_id=self.run_id,
                            booking_id=booking['booking_id'],status='failed' if failed else 'recorded',
                            operation_id=operation_id,state_revision=revision)
                        self._put(db,'confirmation',obj,booking['booking_id'])
                        if failed:
                            disposition, code = 'failed','message_failure'
                            response = {'status':'failed','code':'message_failure'}
                            self._event(db,'confirmation.failed',dict(booking_id=booking['booking_id'],code=code,state_revision=revision),operation_id)
                        else:
                            response = {'status':'recorded','confirmation_id':obj['confirmation_id']}
                            self._event(db,'confirmation.recorded',{k:obj[k] for k in ('confirmation_id','booking_id','state_revision')},operation_id)
                if disposition in ('denied','failed','pending') and response.get('status') == 'failed':
                    response = {'status':'failed','code':code or 'unresolved_operation'}
                # All tool completion/unknown receipts are in the same transaction as the mutation.
                if response.get('status') == 'unknown':
                    self._event(db,'tool.response_unknown',dict(tool=tool,call_id=call_id,code=response['code']),operation_id)
                else:
                    self._event(db,'tool.completed',dict(tool=tool,call_id=call_id,response=response),operation_id)
                attempt = dict(sequence=len(previous)+1,at_ms=run['clock']-1,tool=tool,call_id=call_id,
                    args_sha256=digest(args),idempotency_key=args.get('idempotency_key'),disposition=disposition,
                    operation_id=operation_id,state_revision=revision,fault_code=code)
                validate(attempt,'attempt')
                db.execute('INSERT INTO outcomes(request_seq,body,response) VALUES(?,?,?)',(seq,canonical(attempt).decode(),canonical(response).decode()))
                db.execute('UPDATE runs SET revision=? WHERE id=?',(revision,self.run_id))
                return response

    def close(self):
        with self._sandbox.lock, self._sandbox.db() as db:
            db.execute('UPDATE runs SET closed=1 WHERE id=?',(self.run_id,))

    def snapshot(self):
        with self._sandbox.lock, self._sandbox.db() as db:
            run = self._run(db)
            attempts=[]
            rows=db.execute('SELECT r.*,o.body AS outcome FROM requests r LEFT JOIN outcomes o ON r.seq=o.request_seq WHERE r.run_id=? ORDER BY r.seq',(self.run_id,))
            for index,row in enumerate(rows,1):
                request=parse(row['body'])
                attempts.append(parse(row['outcome']) if row['outcome'] else dict(sequence=index,at_ms=row['at_ms'],
                    tool=request['tool'],call_id=row['call_id'],args_sha256=digest(request['args']),
                    idempotency_key=request['args'].get('idempotency_key'),disposition='pending',
                    operation_id=row['operation_id'],state_revision=None,fault_code=None))
            result=dict(kind='state',schema_version='0.1.0',run_id=self.run_id,journey_id=run['journey'],
                state_revision=run['revision'],closed=bool(run['closed']),
                permissions=[parse(x[0]) for x in db.execute('SELECT body FROM permissions WHERE run_id=? ORDER BY seq',(self.run_id,))],
                reservations=self._objects(db,'reservation'),bookings=self._objects(db,'booking'),
                confirmations=self._objects(db,'confirmation'),attempts=attempts,extensions={})
            return validate(result)

    def events(self):
        with self._sandbox.db() as db:
            return [parse(x[0]) for x in db.execute('SELECT body FROM events WHERE run_id=? ORDER BY seq',(self.run_id,))]

class AuditHandle:
    def __init__(self, handle): self._handle=handle
    def snapshot(self): return self._handle.snapshot()
    def events(self): return self._handle.events()
