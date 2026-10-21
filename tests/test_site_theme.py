"""Regression checks for the After Dark templates and their existing form flows.

Run: python -m unittest discover -s tests -p test_site_theme.py
Uses temporary SQLite databases; no real accounts or payment services are used.
"""
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def isolated_app(directory):
    """Configure local databases before importing the application."""
    os.environ['DATABASE_URL'] = ''
    os.environ['APP_ENV'] = 'development'
    os.environ['STRIPE_SECRET_KEY'] = ''
    os.environ['RESEND_API_KEY'] = ''
    from config import Config
    Config.SQLITE_PATH = str(Path(directory) / 'site.db')
    Config.ADMIN_USERNAME = 'theme-test-admin'
    Config.ENABLE_SCORES = True
    Config.RATE_LIMIT_ENABLED = False
    Config.TRUSTED_HOSTS = None
    Config.SESSION_COOKIE_SECURE = False
    from werblers_engine import database as game_db
    game_db._SQLITE_PATH = str(Path(directory) / 'games.db')
    from app import app
    app.config.update(TESTING=True, BCRYPT_LOG_ROUNDS=4)
    from models.user import User
    from models.db import get_conn
    from routes.pulse import _save_poll
    with app.test_request_context('/'):
        user = User.create('theme-test-admin', 'theme-test@example.invalid', 'local-theme-test-password')
        with get_conn() as conn:
            cur = conn.cursor()
            poll_id = _save_poll(cur, 'Preview poll: game night', [
                {'text': 'What are we playing tonight?', 'options': ['Werblers', 'Battle Chess', 'Party Games', 'Family Sudoku']}
            ])
            cur.execute('SELECT id FROM poll_questions WHERE poll_id = ?', (poll_id,))
            question_id = cur.fetchone()[0]
            cur.execute('SELECT id FROM poll_options WHERE question_id = ? ORDER BY option_order', (question_id,))
            option_id = cur.fetchone()[0]
    return app, {'user_id': user.id, 'poll_id': poll_id, 'question_id': question_id, 'option_id': option_id}


class SiteThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = patch.dict(os.environ)
        cls.env.start()
        cls.tmp = tempfile.TemporaryDirectory(prefix='ronpon-theme-')
        cls.app, cls.fixture = isolated_app(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        cls.env.stop()

    def setUp(self):
        self.client = self.app.test_client()

    def sign_in(self):
        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.fixture['user_id'])
            session['_fresh'] = True

    def csrf(self, response):
        return re.search(r'<meta name="csrf-token" content="([^"]+)"', response.text)[1]

    def test_all_templates_compile_and_public_pages_render(self):
        for name in self.app.jinja_env.list_templates():
            with self.subTest(template=name):
                self.app.jinja_env.get_template(name)
        for path in ['/', '/games/', '/videos/', '/thepulse/', '/thepulse/polls', '/shop/',
                     '/shop/pulse-question', '/shop/payment-success', '/contact', '/login',
                     '/games/party/', '/games/tic-tac-toe', '/games/family-sudoku',
                     '/games/battle-chess', '/games/werblers', '/games/werblers-mobile', '/scores/']:
            with self.subTest(path=path):
                response = self.client.get(path, follow_redirects=True)
                self.assertEqual(response.status_code, 200)
                self.assertIn('after-dark', response.text)
        response = self.client.get('/no-such-channel')
        self.assertEqual(response.status_code, 404)
        self.assertIn('No signal.', response.text)

    def test_homepage_destinations_work_without_javascript(self):
        response = self.client.get('/')
        self.assertEqual(response.text.count('data-broadcast='), 4)
        for destination in ['/games/', '/videos/', '/thepulse', '/shop/']:
            self.assertIn(f'href="{destination}"', response.text)
        self.assertIn('data-dial', response.text)
        self.assertIn('id="programme-guide"', response.text)
        self.assertIn('That’s what you said three games ago.', response.text)
        self.assertNotIn('built-in method', response.text)

    def test_account_and_admin_templates_render(self):
        self.sign_in()
        poll = self.fixture['poll_id']
        for path in ['/profile', '/videos/add', '/thepulse/create',
                     f'/thepulse/polls/{poll}', f'/thepulse/polls/{poll}/edit',
                     f'/thepulse/polls/{poll}/results', '/shop/supporters',
                     '/shop/pulse-question/submissions']:
            with self.subTest(path=path):
                response = self.client.get(path, follow_redirects=True)
                self.assertEqual(response.status_code, 200)
                self.assertIn('after-dark.css', response.text)

    def test_admin_login_still_requires_csrf_and_signs_in(self):
        response = self.client.get('/login')
        form = {'username': 'theme-test-admin', 'password': 'local-theme-test-password'}
        self.assertEqual(self.client.post('/login', data=form).status_code, 400)
        form['csrf_token'] = self.csrf(response)
        result = self.client.post('/login', data=form, follow_redirects=True)
        self.assertEqual(result.status_code, 200)
        with self.client.session_transaction() as session:
            self.assertEqual(session['_user_id'], str(self.fixture['user_id']))

    def test_poll_vote_review_and_submit_remain_functional(self):
        self.sign_in()
        poll = self.fixture['poll_id']
        response = self.client.get(f'/thepulse/polls/{poll}')
        token = self.csrf(response)
        result = self.client.post(f'/thepulse/polls/{poll}/vote', data={
            'csrf_token': token, 'step': 1,
            'question_id': self.fixture['question_id'], 'option_id': self.fixture['option_id'],
        }, follow_redirects=True)
        self.assertEqual(result.status_code, 200)
        self.assertIn('after-dark.css', result.text)
        result = self.client.post(f'/thepulse/polls/{poll}/submit', data={'csrf_token': token}, follow_redirects=True)
        self.assertEqual(result.status_code, 200)
        from models.db import get_conn
        with get_conn() as conn:
            row = conn.execute('SELECT COUNT(*) FROM poll_submissions WHERE poll_id = ? AND user_id = ?',
                               (poll, self.fixture['user_id'])).fetchone()
            self.assertEqual(row[0], 1)

    def test_party_host_and_guest_can_join_same_room(self):
        token = self.csrf(self.client.get('/games/party/'))
        response = self.client.post('/games/party/rooms', data={
            'csrf_token': token, 'game_key': 'lobby-test', 'host_name': 'Host',
        })
        self.assertEqual(response.status_code, 302)
        host_path = response.headers['Location']
        self.assertTrue(host_path.endswith('/host'))
        code = host_path.split('/')[-2]
        host = self.client.get(host_path)
        self.assertEqual(host.status_code, 200)
        self.assertIn('after-dark.css', host.text)
        guest = self.app.test_client()
        token = self.csrf(guest.get('/games/party/'))
        response = guest.post('/games/party/join', data={
            'csrf_token': token, 'code': code, 'name': 'Guest',
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('after-dark.css', response.text)
        state = self.client.get(f'/games/party/api/rooms/{code}').get_json()
        self.assertEqual({p['name'] for p in state['players']}, {'Host', 'Guest'})


if __name__ == '__main__':
    unittest.main()
