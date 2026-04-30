import sys
sys.path.insert(0, '/app')
from utils.date_parser import extract_dates_from_text, extract_group_size_from_text

print('=== TESTES FINAIS ===')

casos = [
    ('entre 15 e 17/07', '15/07/2026', '17/07/2026'),
    ('de 01/05 ate 03/05', '01/05/2026', '03/05/2026'),
    ('do dia 20 ao dia 22 de agosto', '20/08/2026', '22/08/2026'),
    ('de amanha ate depois de amanha', None, None),  # relativos ok
    ('1 de maio a 3 de maio', '01/05/2026', '03/05/2026'),
]

all_ok = True
for txt, exp_ci, exp_co in casos:
    ci, co = extract_dates_from_text(txt)
    if exp_ci is None:
        ok = ci is not None
    else:
        ok = ci == exp_ci and co == exp_co
    status = '✅' if ok else '❌'
    if not ok:
        all_ok = False
    print(f"{status} '{txt}' -> {ci} / {co}")

print()
grupos = [('somos 3', 3), ('casal', 2), ('sozinho', 1), ('família de 4', 4)]
for txt, expected in grupos:
    result = extract_group_size_from_text(txt)
    ok = result == expected
    if not ok: all_ok = False
    print(f"{'✅' if ok else '❌'} '{txt}' -> {result} (esperado {expected})")

print()
if all_ok:
    print('✅ TODOS OS TESTES PASSARAM!')
else:
    print('❌ ALGUNS TESTES FALHARAM')
