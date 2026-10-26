"""Suite letter grade over the seven frozen cases. Unknown evidence never earns a pass."""
import html
from .scenarios import IDS

POLICY_ID='suite-grade-0.1.0'
# A double booking or a booking the caller never agreed to caps the whole suite at D.
MANDATORY=('duplicate-write-prevention','unknown-write-reconciliation','no-consent-no-write')
LETTERS='ABCDF'
SCOPE=('Functional booking outcomes on synthetic tools only. Speech, timing, listening and '
       'repeatability are graded separately and are not part of this letter. Not a certification.')

def scenario_verdict(results):
    """Every run of a case must pass. A known false final status fails the case."""
    verdicts=[]
    for result in results:
        functional=result['dimensions']['functional']
        if result['dimensions']['truthfulness']=='fail': functional='fail'
        verdicts.append(functional)
    return 'fail' if 'fail' in verdicts else 'unknown' if 'unknown' in verdicts else 'pass'

def letter_for(passed):
    return LETTERS[min(max(len(IDS)-passed,0),4)]

def grade(runs):
    """runs: iterable of (scenario_id, run_id, result)."""
    by_case={key:[] for key in IDS}
    for scenario_id,run_id,result in runs:
        by_case[scenario_id].append((run_id,result))
    rows=[]
    for key in IDS:
        verdict=scenario_verdict([r for _,r in by_case[key]]) if by_case[key] else 'not_run'
        failed=sorted({c['check_id'] for _,r in by_case[key] for c in r['checks'] if c['verdict']=='fail'})
        rows.append(dict(scenario_id=key,mandatory=key in MANDATORY,verdict=verdict,
                         runs=[rid for rid,_ in by_case[key]],failed_checks=failed))
    passed=sum(row['verdict']=='pass' for row in rows)
    missing=[row['scenario_id'] for row in rows if row['verdict']=='not_run']
    mandatory_missed=[row['scenario_id'] for row in rows if row['mandatory'] and row['verdict']!='pass']
    letter=None if missing else letter_for(passed)
    capped=bool(letter in ('A','B','C') and mandatory_missed)
    if capped: letter='D'
    return dict(kind='grade',schema_version='0.1.0',policy_id=POLICY_ID,letter=letter,passed=passed,
                total=len(IDS),capped_by_mandatory=capped,mandatory_not_passed=mandatory_missed,missing_scenarios=missing,scenarios=rows,scope=SCOPE)

def exit_code(card,min_grade=None):
    if card['letter'] is None: return 2
    if min_grade: return 0 if LETTERS.index(card['letter'])<=LETTERS.index(min_grade) else 1
    verdicts={row['verdict'] for row in card['scenarios']}
    return 1 if 'fail' in verdicts else 2 if 'unknown' in verdicts else 0

def markdown(card):
    head=('# SMB voice bench grade: '+card['letter'] if card['letter'] else '# SMB voice bench grade: incomplete')
    lines=[head,'',f"{card['passed']} of {card['total']} cases passed."]
    if card['capped_by_mandatory']: lines.append('Capped at D: a mandatory case (double booking or booking without consent) did not pass.')
    if card['missing_scenarios']: lines.append('No letter: every case must be run. Missing: '+', '.join(card['missing_scenarios'])+'.')
    lines+=['','| Case | Mandatory | Verdict | Failed checks |','| --- | --- | --- | --- |']
    for row in card['scenarios']:
        lines.append(f"| `{row['scenario_id']}` | {'yes' if row['mandatory'] else ''} | {row['verdict']} | {', '.join(row['failed_checks'])} |")
    lines+=['',card['scope'],'']
    return '\n'.join(lines)

COLORS={'A':'#2e7d32','B':'#558b2f','C':'#f9a825','D':'#ef6c00','F':'#c62828',None:'#757575'}

def badge(card):
    value=(card['letter'] or 'incomplete')+f" {card['passed']}/{card['total']}"
    label='smb voice bench'
    lw=7*len(label)+10; vw=7*len(value)+10; width=lw+vw
    text=html.escape(label+': '+value,quote=True)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="20" role="img" aria-label="{text}">'
            f'<title>{text}</title><rect width="{lw}" height="20" fill="#555"/>'
            f'<rect x="{lw}" width="{vw}" height="20" fill="{COLORS[card["letter"]]}"/>'
            '<g fill="#fff" font-family="Verdana,DejaVu Sans,sans-serif" font-size="11" text-anchor="middle">'
            f'<text x="{lw/2}" y="14">{html.escape(label)}</text><text x="{lw+vw/2}" y="14">{html.escape(value)}</text></g></svg>\n')
