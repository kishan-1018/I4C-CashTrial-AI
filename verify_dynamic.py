import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE = 'http://127.0.0.1:8000'

def test_full_system():
    # 1. Check index.html
    html = urllib.request.urlopen(f'{BASE}/').read().decode()
    assert 'modal-intake-backdrop' in html, "modal-intake-backdrop missing"
    assert 'scam-tile' in html, "scam-tile missing"
    assert 'time-pill-btn' in html, "time-pill-btn missing"
    assert 'dest-choice-auto' in html, "dest-choice-auto missing"
    assert 'dest-choice-custom' in html, "dest-choice-custom missing"
    print('✓ index.html verified with citizen modal and dynamic controls')

    # 2. Check static JS & CSS
    for asset in ['/static/css/dashboard.css', '/static/js/map.js', '/static/js/app.js']:
        res = urllib.request.urlopen(f'{BASE}{asset}')
        assert res.status == 200
        content = res.read().decode()
        assert len(content) > 1000
        print(f'✓ {asset} served successfully ({len(content)} bytes)')

    # 3. Test arbitrary Pan-India dynamic intake (Sikkim to Punjab)
    data = json.dumps({
        'scam_category': 'SEXTORTION_VIDEO_BLACKMAIL',
        'disputed_amount_inr': 180000.0,
        'origin_state': 'Sikkim',
        'origin_district': 'Gangtok',
        'destination_state': 'Punjab',
        'destination_district': 'Ludhiana',
        'preferred_touchpoint_modality': 'WHITE_LABEL_ATM',
        'reporting_delay_minutes': 22,
        'primary_utr': '429911223344',
        'num_mule_hops': 4
    }).encode('utf-8')
    req = urllib.request.Request(f'{BASE}/api/simulate-incident', data=data, headers={'Content-Type': 'application/json'})
    res = urllib.request.urlopen(req)
    resp_data = json.loads(res.read().decode())
    assert resp_data['status'] == 'INGESTED_SUCCESSFULLY'
    cid = resp_data['incident']['complaint_id']
    ds = resp_data['decision_support']
    traj = ds['trajectory']
    print(f'✓ Dynamic Incident created: {cid}')
    print(f'  Origin: {traj["origin"]["district"]}, {traj["origin"]["state"]} @ {traj["origin"]["coordinates"]}')
    print(f'  Transit Hops: {len(traj["transit_hops"])} multi-state hops tracked')
    print(f'  Destination: {traj["destination"]["corridor_name"]} @ {traj["destination"]["coordinates"]}')
    print(f'  Candidate Touchpoints: {len(traj["candidate_touchpoints"])} synthesized in Punjab')
    for idx, tp in enumerate(traj['candidate_touchpoints'][:3]):
        print(f'    #{idx+1}: {tp["institution_name"]} ({tp["touchpoint_type"]}) | PS: {tp["police_jurisdiction"]} | CCTV: {tp["cctv_available"]} | Score: {tp["ranking_score"]}')

    # 4. Check Incident Analysis Endpoint
    res_an = urllib.request.urlopen(f'{BASE}/api/incident-analysis/{cid}')
    assert res_an.status == 200
    an_data = json.loads(res_an.read().decode())
    assert 'decision_support' in an_data
    assert 'trajectory' in an_data['decision_support']
    print('✓ Incident analysis endpoint returns complete trajectory for GIS Map')

    print('\n🎉 ALL DYNAMIC PAN-INDIA INTAKE & TRACKING VERIFICATIONS PASSED!')

if __name__ == '__main__':
    test_full_system()
