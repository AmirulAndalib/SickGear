import requests
import certifi
import sickgear
import time
import datetime
import logging
from exceptions_helper import ex, ConnectionSkipException
from json_helper import json_dumps
from sg_helpers import get_url, try_int

from .exceptions import *

# noinspection PyUnreachableCode
if False:
    from typing import Any, AnyStr, Dict

log = logging.getLogger('api_trakt')
log.addHandler(logging.NullHandler())


class TraktAccount(object):
    max_auth_fail = 9

    def __init__(self, account_id=None, token='', refresh_token='', auth_fail=0, last_fail=None, token_valid_date=None):
        self.account_id = account_id
        self._name = ''
        self._slug = ''
        self.token = token
        self.refresh_token = refresh_token
        self.auth_fail = auth_fail
        self.last_fail = last_fail
        self.token_valid_date = token_valid_date

    def get_name_slug(self):
        try:
            resp = TraktAPI().trakt_request('users/settings', send_oauth=self.account_id, sleep_retry=20)
            self.reset_auth_failure()
            if 'user' in resp:
                self._name = resp['user']['username']
                self._slug = resp['user']['ids']['slug']
        except TraktAuthException:
            self.inc_auth_failure()
            self._name = ''
        except (TraktException, ConnectionSkipException, BaseException, Exception):
            pass

    @property
    def slug(self):
        if self.token and self.active:
            if not self._slug:
                self.get_name_slug()
        else:
            self._slug = ''
        return self._slug

    @property
    def name(self):
        if self.token and self.active:
            if not self._name:
                self.get_name_slug()
        else:
            self._name = ''

        return self._name

    def reset_name(self):
        self._name = ''

    @property
    def active(self):
        return self.auth_fail < self.max_auth_fail and self.token

    @property
    def needs_refresh(self):
        return not self.token_valid_date or self.token_valid_date - datetime.datetime.now() < datetime.timedelta(days=3)

    @property
    def token_expired(self):
        return self.token_valid_date and self.token_valid_date < datetime.datetime.now()

    def reset_auth_failure(self):
        if 0 != self.auth_fail:
            self.auth_fail = 0
            self.last_fail = None

    def inc_auth_failure(self):
        self.auth_fail += 1
        self.last_fail = datetime.datetime.now()

    def auth_failure(self):
        if self.auth_fail < self.max_auth_fail:
            if self.last_fail:
                time_diff = datetime.datetime.now() - self.last_fail
                if 0 == self.auth_fail % 3:
                    if datetime.timedelta(days=1) < time_diff:
                        self.inc_auth_failure()
                        sickgear.save_config()
                elif datetime.timedelta(minutes=15) < time_diff:
                    self.inc_auth_failure()
                    if self.auth_fail == self.max_auth_fail or datetime.timedelta(hours=6) < time_diff:
                        sickgear.save_config()
            else:
                self.inc_auth_failure()


class TraktAPI(object):
    max_retrys = 3

    def __init__(self, timeout=None):

        self.session = requests.Session()
        self.verify = sickgear.TRAKT_VERIFY and certifi.where()
        self.timeout = timeout or sickgear.TRAKT_TIMEOUT
        self.auth_url = sickgear.TRAKT_BASE_URL
        self.api_url = sickgear.TRAKT_BASE_URL
        self.headers = {'Content-Type': 'application/json',
                        'trakt-api-version': '2',
                        'trakt-api-key': sickgear.TRAKT_CLIENT_ID}

    @staticmethod
    def build_config_string(data):
        return '!!!'.join('%s|%s|%s|%s|%s|%s' % (
            value.account_id, value.token, value.refresh_token, value.auth_fail,
            value.last_fail.strftime('%Y%m%d%H%M') if value.last_fail else '0',
            value.token_valid_date.strftime('%Y%m%d%H%M%S') if value.token_valid_date else '0')
                          for (key, value) in data.items())

    @staticmethod
    def read_config_string(data):
        return dict((int(a.split('|')[0]), TraktAccount(
            int(a.split('|')[0]), a.split('|')[1], a.split('|')[2], int(a.split('|')[3]),
            datetime.datetime.strptime(a.split('|')[4], '%Y%m%d%H%M') if a.split('|')[4] != '0' else None,
            datetime.datetime.strptime(a.split('|')[5], '%Y%m%d%H%M%S') if a.split('|')[5] != '0' else None))
                    for a in data.split('!!!') if data)

    @staticmethod
    def add_account(token, refresh_token, token_valid_date):
        k = max(sickgear.TRAKT_ACCOUNTS.keys() or [0]) + 1
        sickgear.TRAKT_ACCOUNTS[k] = TraktAccount(account_id=k, token=token, refresh_token=refresh_token,
                                                   token_valid_date=token_valid_date)
        sickgear.save_config()
        return k

    @staticmethod
    def replace_account(account, token, refresh_token, token_valid_date, refresh):
        if account in sickgear.TRAKT_ACCOUNTS:
            sickgear.TRAKT_ACCOUNTS[account].token = token
            sickgear.TRAKT_ACCOUNTS[account].refresh_token = refresh_token
            sickgear.TRAKT_ACCOUNTS[account].token_valid_date = token_valid_date
            if not refresh:
                sickgear.TRAKT_ACCOUNTS[account].reset_name()
            sickgear.TRAKT_ACCOUNTS[account].reset_auth_failure()
            sickgear.save_config()
            return True
        return False

    @staticmethod
    def delete_account(account):
        if account in sickgear.TRAKT_ACCOUNTS:
            try:
                TraktAPI().trakt_request('/oauth/revoke', send_oauth=account, method='POST')
            except (TraktException, BaseException, Exception) as e:
                log.info('Failed to remove account from trakt.tv: %s' % e)
                return False
            sickgear.TRAKT_ACCOUNTS.pop(account)
            sickgear.save_config()
            return True
        return False

    def trakt_token(self, trakt_pin=None, refresh=False, count=0, account=None):
        if self.max_retrys <= count:
            return False
        0 < count and time.sleep(3)

        data = {
            'client_id': sickgear.TRAKT_CLIENT_ID,
            'client_secret': sickgear.TRAKT_CLIENT_SECRET,
            'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob'
        }

        if refresh:
            if None is not account and account in sickgear.TRAKT_ACCOUNTS:
                data['grant_type'] = 'refresh_token'
                data['refresh_token'] = sickgear.TRAKT_ACCOUNTS[account].refresh_token
            else:
                return False
        else:
            data['grant_type'] = 'authorization_code'
            if trakt_pin:
                data['code'] = trakt_pin

        headers = {'Content-Type': 'application/json'}

        try:
            now = datetime.datetime.now()
            resp = self.trakt_request('oauth/token', data=data, headers=headers, url=self.auth_url,
                                      count=count, sleep_retry=0)
        except TraktInvalidGrant:
            if None is not account and account in sickgear.TRAKT_ACCOUNTS:
                sickgear.TRAKT_ACCOUNTS[account].token = ''
                sickgear.TRAKT_ACCOUNTS[account].refresh_token = ''
                sickgear.TRAKT_ACCOUNTS[account].token_valid_date = None
                sickgear.save_config()
            return False
        except (TraktAuthException, TraktException):
            return False

        if 'access_token' in resp and 'refresh_token' in resp and 'expires_in' in resp:
            token_valid_date = now + datetime.timedelta(seconds=try_int(resp['expires_in']))
            if refresh or (not refresh and None is not account and account in sickgear.TRAKT_ACCOUNTS):
                return self.replace_account(account, resp['access_token'], resp['refresh_token'],
                                            token_valid_date, refresh)
            return self.add_account(resp['access_token'], resp['refresh_token'], token_valid_date)

        return False

    def trakt_request(self, path, data=None, headers=None, url=None, count=0, sleep_retry=60,
                      send_oauth=None, method=None, raise_skip_exception=True, failure_monitor=True, **kwargs):
        # type: (AnyStr, Dict, Dict, AnyStr, int, int, AnyStr, AnyStr, bool, bool, Any) -> Dict

        if method not in ['GET', 'POST', 'PUT', 'DELETE', None]:
            return {}
        if None is method:
            method = ('GET', 'POST')['data' in kwargs.keys() or None is not data]
        if 'oauth/token' != path and None is send_oauth and method in ['POST', 'PUT', 'DELETE']:
            return {}

        count += 1
        if count > self.max_retrys:
            return {}

        # wait before retry
        if 'users/settings' != path:
            1 < count and time.sleep(sleep_retry)

        headers = headers or self.headers
        if None is not send_oauth and send_oauth in sickgear.TRAKT_ACCOUNTS:
            if sickgear.TRAKT_ACCOUNTS[send_oauth].active:
                if sickgear.TRAKT_ACCOUNTS[send_oauth].needs_refresh:
                    self.trakt_token(refresh=True, count=0, account=send_oauth)
                if sickgear.TRAKT_ACCOUNTS[send_oauth].token_expired or \
                        not sickgear.TRAKT_ACCOUNTS[send_oauth].active:
                    return {}
                headers['Authorization'] = 'Bearer %s' % sickgear.TRAKT_ACCOUNTS[send_oauth].token
            else:
                return {}

        kwargs = dict(headers=headers, timeout=self.timeout, verify=self.verify)
        if data:
            kwargs['data'] = json_dumps(data)

        url = url or self.api_url
        try:
            resp = get_url('%s%s' % (url, path), session=self.session, use_method=method, return_response=True,
                           raise_exceptions=True, raise_status_code=True, raise_skip_exception=raise_skip_exception,
                           failure_monitor=failure_monitor, **kwargs)

            if 'DELETE' == method:
                result = None
                if 204 == resp.status_code:
                    result = {'result': 'success'}
                elif 404 == resp.status_code:
                    result = {'result': 'failed'}
                if result and None is not send_oauth and send_oauth in sickgear.TRAKT_ACCOUNTS:
                    sickgear.TRAKT_ACCOUNTS[send_oauth].reset_auth_failure()
                    return result
                resp.raise_for_status()
                return {}

            # check for http errors and raise if any are present
            resp.raise_for_status()

            # convert response to json
            resp = resp.json()

        except requests.RequestException as e:
            code = getattr(e.response, 'status_code', None)
            if not code:
                if 'timed out' in ex(e):
                    log.warning('Timeout connecting to Trakt')
                    if count >= self.max_retrys:
                        raise TraktTimeout()
                    return self.trakt_request(path, data, headers, url, count=count, sleep_retry=sleep_retry,
                                              send_oauth=send_oauth, method=method)
                # This is pretty much a fatal error if there is no status_code
                # It means there basically was no response at all
                else:
                    log.warning('Could not connect to Trakt. Error: %s' % ex(e))
                    raise TraktException('Could not connect to Trakt. Error: %s' % ex(e))

            elif 502 == code:
                # Retry the request, Cloudflare had a proxying issue
                log.warning(f'Retrying Trakt api request: {path}')
                if count >= self.max_retrys:
                    raise TraktCloudFlareException()
                return self.trakt_request(path, data, headers, url, count=count, sleep_retry=sleep_retry,
                                          send_oauth=send_oauth, method=method)

            elif 401 == code and 'oauth/token' != path:
                if None is not send_oauth:
                    if sickgear.TRAKT_ACCOUNTS[send_oauth].needs_refresh:
                        if self.trakt_token(refresh=True, count=count, account=send_oauth):
                            return self.trakt_request(path, data, headers, url, count=count, sleep_retry=sleep_retry,
                                                      send_oauth=send_oauth, method=method)

                        log.warning('Unauthorized. Please check your Trakt settings')
                        sickgear.TRAKT_ACCOUNTS[send_oauth].auth_failure()
                        raise TraktAuthException()

                    # sometimes the trakt server sends invalid token error even if it isn't
                    sickgear.TRAKT_ACCOUNTS[send_oauth].auth_failure()
                    if count >= self.max_retrys:
                        raise TraktAuthException()

                    return self.trakt_request(path, data, headers, url, count=count, sleep_retry=sleep_retry,
                                              send_oauth=send_oauth, method=method)

                raise TraktAuthException()
            elif code in (500, 501, 503, 504, 520, 521, 522):
                if count >= self.max_retrys:
                    log.warning(f'Trakt may have some issues and it\'s unavailable. Code: {code}')
                    raise TraktServerError(error_code=code)
                # http://docs.trakt.apiary.io/#introduction/status-codes
                log.warning('Trakt may have some issues and it\'s unavailable. Trying again')
                return self.trakt_request(path, data, headers, url, count=count, sleep_retry=sleep_retry,
                                          send_oauth=send_oauth, method=method)
            elif 404 == code:
                # log.debug(f'Trakt error (404) the resource does not exist: {url}{path}')
                raise TraktMethodNotExisting('Trakt error (404) the resource does not exist: %s%s' % (url, path))
            elif 429 == code:
                if count >= self.max_retrys:
                    log.warning('Trakt replied with Rate-Limiting, maximum retries exceeded.')
                    raise TraktServerError(error_code=code)
                r_headers = getattr(e.response, 'headers', None)
                if None is not r_headers:
                    wait_seconds = min(try_int(r_headers.get('Retry-After', 60), 60), 150)
                else:
                    wait_seconds = 60
                log.warning('Trakt replied with Rate-Limiting, waiting %s seconds.' % wait_seconds)
                wait_seconds = (wait_seconds, 60)[0 > wait_seconds]
                wait_seconds -= sleep_retry
                if 0 < wait_seconds:
                    time.sleep(wait_seconds)
                return self.trakt_request(path, data, headers, url, count=count, sleep_retry=sleep_retry,
                                          send_oauth=send_oauth, method=method)
            elif 423 == code:
                # locked account
                log.error('An application that is NOT SickGear has flooded the Trakt API and they have locked access'
                          ' to your account. They request you contact their support at https://support.trakt.tv/'
                          ' This is not a fault of SickGear because it does *not* sync data or send the type of data'
                          ' that triggers a Trakt access lock.'
                          ' SickGear may only send a notification on a media process completion if set up for it.')
                raise TraktLockedUserAccount()
            elif 400 == code and 'invalid_grant' in getattr(e, 'text', ''):
                raise TraktInvalidGrant('Error: invalid_grant. The provided authorization grant is invalid, expired, '
                                        'revoked, does not match the redirection URI used in the authorization request,'
                                        ' or was issued to another client.')
            elif 420 == code and 'sync/collection' in path:
                # collections are limited to 100 items
                raise TraktFreemiumLimit('Freemium account maximum items exceeded')
            else:
                log.error('Could not connect to Trakt. Code error: {0}'.format(code))
                raise TraktException('Could not connect to Trakt. Code error: %s' % code)
        except ConnectionSkipException as e:
            log.warning('Connection is skipped')
            raise e
        except ValueError as e:
            log.error(f'Value Error: {ex(e)}')
            raise TraktValueError(f'Value Error: {ex(e)}')
        except (BaseException, Exception) as e:
            log.error('Exception: %s' % ex(e))
            raise TraktException('Could not connect to Trakt. Code error: %s' % ex(e))

        # check and confirm Trakt call did not fail
        if isinstance(resp, dict) and 'failure' == resp.get('status', None):
            if 'message' in resp:
                raise TraktException(resp['message'])
            if 'error' in resp:
                raise TraktException(resp['error'])
            raise TraktException('Unknown Error')

        if None is not send_oauth and send_oauth in sickgear.TRAKT_ACCOUNTS:
            sickgear.TRAKT_ACCOUNTS[send_oauth].reset_auth_failure()
        return resp
