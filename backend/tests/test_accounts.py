"""Account authentication and persistent, account-scoped question history."""
import httpx
import pytest

from app.db import connect, init_db, transaction
from app.main import create_app
from app.models import MatchCreateIn
from app.schema import SCHEMA_VERSION
from app.services.matches import create_match, open_tile
from app.services.selector import eligible_questions
from tests.conftest import SIX_CATEGORIES, make_installation_row


async def register(client, username="player-one"):
    response = await client.post('/api/v1/auth/register', json={
        'username': username, 'password': 'a long test password',
    }, headers={'X-Requested-With': 'SeenJeem'})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_register_login_logout_and_persistence(client, seeded_settings):
    account = await register(client)
    assert account['user']['username'] == 'player-one'
    assert account['questions_seen'] == 0
    cookie = client.cookies.get('seenjeem_session')
    assert cookie
    me = await client.get('/api/v1/auth/me')
    assert me.json()['user']['id'] == account['user']['id']
    async with connect(seeded_settings) as db:
        row = await (await db.execute('SELECT password_hash FROM users WHERE id = ?', (account['user']['id'],))).fetchone()
        assert row['password_hash'] and 'a long test password' not in row['password_hash']
        sessions = await (await db.execute('SELECT token_hash FROM account_sessions')).fetchall()
        assert all(row['token_hash'] != cookie for row in sessions)
    await init_db(seeded_settings)
    assert (await client.get('/api/v1/auth/me')).status_code == 200
    out = await client.post('/api/v1/auth/logout', headers={'X-Requested-With': 'SeenJeem'})
    assert out.status_code == 200
    assert (await client.get('/api/v1/auth/me')).status_code == 401
    client.cookies.set('seenjeem_session', cookie)
    assert (await client.get('/api/v1/auth/me')).status_code == 401
    client.cookies.clear()
    response = await client.post('/api/v1/auth/login', json={
        'username': 'PLAYER-ONE', 'password': 'a long test password',
    }, headers={'X-Requested-With': 'SeenJeem'})
    assert response.status_code == 200
    assert response.json()['user']['id'] == account['user']['id']


@pytest.mark.asyncio
async def test_invalid_credentials_duplicates_and_csrf(client):
    await register(client)
    duplicate = await client.post('/api/v1/auth/register', json={
        'username': 'PLAYER-ONE', 'password': 'another long password',
    }, headers={'X-Requested-With': 'SeenJeem'})
    assert duplicate.status_code == 409
    shadow_name = await client.post('/api/v1/users', json={'username': 'PLAYER-ONE'})
    assert shadow_name.status_code == 409
    for username in ('player-one', 'missing-player'):
        response = await client.post('/api/v1/auth/login', json={
            'username': username, 'password': 'wrong password',
        }, headers={'X-Requested-With': 'SeenJeem'})
        assert response.status_code == 401
        assert response.json()['error']['code'] == 'INVALID_CREDENTIALS'
    assert (await client.post('/api/v1/auth/logout')).status_code == 403
    weak = await client.post('/api/v1/auth/register', json={
        'username': 'weak', 'password': '123',
    }, headers={'X-Requested-With': 'SeenJeem'})
    assert weak.status_code == 422
    profiles = (await client.get('/api/v1/users')).json()
    assert all(user['username'] != 'player-one' for user in profiles)


@pytest.mark.asyncio
async def test_history_follows_account_across_devices_and_other_accounts_are_independent(client, seeded_settings):
    account = await register(client)
    user_id = account['user']['id']
    install_id, _ = await make_installation_row(seeded_settings, 'device-first')
    payload = MatchCreateIn(team1_name='First', team2_name='Second', category_slugs=SIX_CATEGORIES)
    first = await create_match(seeded_settings, payload, 'account-game-first',
                               host_installation_id=install_id, host_user_id=user_id)
    tile = first['tiles'][0]
    async with connect(seeded_settings) as db:
        question = await (await db.execute('SELECT category_id, difficulty FROM questions WHERE id = ?', (tile['question']['id'],))).fetchone()
    await open_tile(seeded_settings, first['match']['match_code'], tile['tile_key'],
                    expected_version=first['match']['version'], idempotency_key='account-open-first',
                    host_token=first['host_token'])
    assert (await client.get('/api/v1/auth/me')).json()['questions_seen'] == 1
    history = (await client.get('/api/v1/auth/history')).json()
    assert history['total'] == 1
    assert history['items'][0]['question_id'] == tile['question']['id']
    # A different browser signs into the same account and gets the same history.
    transport = httpx.ASGITransport(app=create_app(seeded_settings))
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as other:
        response = await other.post('/api/v1/auth/login', json={
            'username': 'player-one', 'password': 'a long test password',
        }, headers={'X-Requested-With': 'SeenJeem'})
        assert response.status_code == 200
        assert (await other.get('/api/v1/auth/me')).json()['questions_seen'] == 1
    # Selection excludes this question even after the device changes and cycles reset.
    async with transaction(seeded_settings) as db:
        await db.execute("UPDATE matches SET status = 'completed'")
        rows = await eligible_questions(db, question['category_id'], question['difficulty'], 999, (user_id,))
        assert tile['question']['id'] not in {row['id'] for row in rows}
    other_account = await register(client, 'player-two')
    assert other_account['questions_seen'] == 0
    async with transaction(seeded_settings) as db:
        rows = await eligible_questions(db, question['category_id'], question['difficulty'], 999, (other_account['user']['id'],))
        assert tile['question']['id'] in {row['id'] for row in rows}
    install2, _ = await make_installation_row(seeded_settings, 'device-second')
    second = await create_match(seeded_settings, payload, 'account-game-second',
                                host_installation_id=install2, host_user_id=user_id)
    assert tile['question']['id'] not in {item['question']['id'] for item in second['tiles'] + second['backups']}


@pytest.mark.asyncio
async def test_match_automatically_binds_authenticated_account_and_rejects_impersonation(client, seeded_settings):
    account = await register(client)
    _, token = await make_installation_row(seeded_settings, 'route-device')
    payload = {'team1_name': 'First', 'team2_name': 'Second', 'category_slugs': SIX_CATEGORIES}
    response = await client.post('/api/v1/matches', json=payload, headers={
        'Idempotency-Key': 'bound-account', 'X-Install-Token': token,
        'X-Requested-With': 'SeenJeem',
    })
    assert response.status_code == 201, response.text
    async with connect(seeded_settings) as db:
        row = await (await db.execute('SELECT host_user_id FROM matches WHERE match_code = ?',
                                      (response.json()['match']['match_code'],))).fetchone()
        assert row['host_user_id'] == account['user']['id']
    await client.post('/api/v1/auth/logout', headers={'X-Requested-With': 'SeenJeem'})
    signed_out = await client.post('/api/v1/matches', json=payload, headers={
        'Idempotency-Key': 'expired-browser-account', 'X-Install-Token': token,
        'X-Account-Required': '1', 'X-Requested-With': 'SeenJeem',
    })
    assert signed_out.status_code == 401
    payload['team1_user_ids'] = [account['user']['id']]
    forged = await client.post('/api/v1/matches', json=payload, headers={
        'Idempotency-Key': 'forged-account', 'X-Install-Token': token,
    })
    assert forged.status_code == 403


@pytest.mark.asyncio
async def test_expired_sessions_are_rejected(client, seeded_settings):
    await register(client)
    async with transaction(seeded_settings) as db:
        await db.execute('UPDATE account_sessions SET expires_at = 0')
    assert (await client.get('/api/v1/auth/me')).status_code == 401


@pytest.mark.asyncio
async def test_login_throttled(client):
    for _ in range(10):
        response = await client.post('/api/v1/auth/login', json={
            'username': 'no-account', 'password': 'wrong password',
        }, headers={'X-Requested-With': 'SeenJeem'})
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_v5_migration_preserves_profiles_and_question_history(seeded_settings):
    from app.services.identity import create_profile
    profile = await create_profile(seeded_settings, username='legacy-player')
    async with transaction(seeded_settings) as db:
        await db.execute('INSERT INTO user_question_history(user_id, question_id) VALUES (?, 1)', (profile['id'],))
        await db.execute('DROP TABLE account_sessions')
        await db.execute('DROP TABLE auth_attempts')
        await db.execute('ALTER TABLE matches DROP COLUMN host_user_id')
        await db.execute('ALTER TABLE users DROP COLUMN password_hash')
        await db.execute('PRAGMA user_version = 5')
    await init_db(seeded_settings)
    async with connect(seeded_settings) as db:
        row = await (await db.execute('SELECT * FROM users WHERE id = ?', (profile['id'],))).fetchone()
        assert row['username'] == 'legacy-player' and row['password_hash'] is None
        assert (await (await db.execute('SELECT COUNT(*) FROM user_question_history WHERE user_id = ?', (profile['id'],))).fetchone())[0] == 1
        assert (await (await db.execute('PRAGMA user_version')).fetchone())[0] == SCHEMA_VERSION


@pytest.mark.asyncio
async def test_exhausted_account_history_never_falls_back_to_seen_questions(client, seeded_settings):
    account = await register(client)
    _, token = await make_installation_row(seeded_settings, 'exhausted-device')
    async with transaction(seeded_settings) as db:
        await db.execute('INSERT INTO user_question_history(user_id, question_id) '
                         'SELECT ?, id FROM questions', (account['user']['id'],))
    response = await client.post('/api/v1/matches', json={
        'team1_name': 'First', 'team2_name': 'Second', 'category_slugs': SIX_CATEGORIES,
    }, headers={'X-Requested-With': 'SeenJeem', 'Idempotency-Key': 'exhausted-game', 'X-Install-Token': token})
    assert response.status_code == 409
    assert response.json()['error']['code'] == 'INSUFFICIENT_QUESTIONS'
    assert response.json()['error']['details']['available'] == 0
    async with connect(seeded_settings) as db:
        assert (await (await db.execute('SELECT COUNT(*) FROM matches')).fetchone())[0] == 0
