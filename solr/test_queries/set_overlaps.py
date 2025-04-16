ids = {}
with open('data/climate_health_ids.txt') as f:
    ids['OpenAlex'] = set(f.readlines())
with open('data/climate_health_ids_db.txt') as f:
    ids['NACSOS'] = set(f.readlines())
with open('data/climate_health_ids_db_rel.txt') as f:
    ids['NACSOS (rel)'] = set(f.readlines())
with open('data/climate_health_pred_incl.txt') as f:
    ids['Predicted'] = set(f.readlines())
for k1, v1 in ids.items():
    print(f'{k1} has {len(v1):,} records')
    for k2, v2 in ids.items():
        if k1 != k2:
            print(f'  {k2} has {len(v2):,} records')
            print(f'   > Union: {len(v1 | v2):,} '
                  f'| intersect: {len(v1 & v2):,} '
                  f'| {k1} exclusive: {len(v1 - v2):,} '
                  f'| {k2} exclusive {len(v2 - v1):,}')