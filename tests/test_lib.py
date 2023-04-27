# coding=UTF-8
# Author: Dennis Lutter <lad1337@gmail.com>
#
# This file is part of SickGear.
#
# SickGear is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SickGear is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SickGear.  If not, see <http://www.gnu.org/licenses/>.

import gc
import glob
import os.path
import shutil
import sqlite3
import sys
import unittest

sys.path.insert(1, os.path.abspath('..'))
sys.path.insert(1, os.path.abspath('../lib'))

import sickgear
from sickgear import db, providers, tvcache
from sickgear.databases import cache_db, failed_db, mainDB

# =================
# test globals
# =================
TESTDIR = os.path.abspath('.')
TESTDBNAME = 'sickbeard.db'
TESTCACHEDBNAME = 'cache.db'
TESTFAILEDDBNAME = 'failed.db'

SHOWNAME = 'show name'
SEASON = 4
EPISODE = 2
FILENAME = f'show name - s0{SEASON}e0{EPISODE}.mkv'
FILEDIR = os.path.join(TESTDIR, SHOWNAME)
FILEPATH = os.path.join(FILEDIR, FILENAME)

SHOWDIR = os.path.join(TESTDIR, SHOWNAME + ' final')

# sickgear.logger.sb_log_instance = sickgear.logger.SBRotatingLogHandler(
#     os.path.join(TESTDIR, 'sickgear.log'), sickgear.logger.NUM_LOGS, sickgear.logger.LOG_SIZE)
sickgear.logger.SBRotatingLogHandler.log_file = os.path.join(os.path.join(TESTDIR, 'Logs'), 'test_sickgear.log')


# =================
# prepare env functions
# =================
def create_test_log_folder():
    if not os.path.isdir(sickgear.LOG_DIR):
        os.mkdir(sickgear.LOG_DIR)


def create_test_cache_folder():
    if not os.path.isdir(sickgear.CACHE_DIR):
        os.mkdir(sickgear.CACHE_DIR)


def remove_test_cache_folder():
    if os.path.isdir(sickgear.CACHE_DIR):
        shutil.rmtree(sickgear.CACHE_DIR, ignore_errors=True)


# call env functions at appropriate time during sickgear var setup

# =================
# sickgear globals
# =================
sickgear.SYS_ENCODING = 'UTF-8'
sickgear.showList = []
sickgear.showDict = {}
sickgear.QUALITY_DEFAULT = 4  # hdtv
sickgear.FLATTEN_FOLDERS_DEFAULT = 0

sickgear.NAMING_PATTERN = ''
sickgear.NAMING_ABD_PATTERN = ''
sickgear.NAMING_SPORTS_PATTERN = ''
sickgear.NAMING_MULTI_EP = 1

sickgear.PROVIDER_ORDER = []
sickgear.newznab_providers = providers.newznab_source_list('')
sickgear.provider_list = providers.provider_modules()

sickgear.PROG_DIR = os.path.abspath('..')
# sickgear.DATA_DIR = os.path.join(sickgear.PROG_DIR, 'tests')
sickgear.DATA_DIR = os.path.join(TESTDIR, 'data')
sickgear.LOG_DIR = os.path.join(TESTDIR, 'Logs')
create_test_log_folder()
sickgear.logger.sb_log_instance.init_logging(False)

sickgear.CACHE_DIR = os.path.join(TESTDIR, 'cache')
sickgear.ZONEINFO_DIR = os.path.join(TESTDIR, 'cache', 'zoneinfo')
create_test_cache_folder()
sickgear.GUI_NAME = 'slick'
sickgear.MEMCACHE = {'history_tab_limit': 10, 'history_tab': []}


# =================
# dummy functions
# =================
def _dummy_save_config():
    return True


# this overrides the save_config which gets called during a db upgrade
# this might be considered a hack
mainDB.sickgear.save_config = _dummy_save_config


# the real one tries to contact tvdb just stop it from getting more info on the ep
# noinspection PyUnusedLocal
def _fake_specify_ep(self, season, episode, show_sql=None, existing_only=False, **kwargs):
    pass


sickgear.tv.TVEpisode.specify_episode = _fake_specify_ep


# =================
# test classes
# =================
class SickbeardTestDBCase(unittest.TestCase):
    def setUp(self):
        create_test_cache_folder()
        sickgear.showList = []
        sickgear.showDict = {}
        setup_test_db()
        setup_test_episode_file()
        setup_test_show_dir()

    def tearDown(self):
        remove_test_cache_folder()
        sickgear.showList = []
        sickgear.showDict = {}
        teardown_test_db()
        teardown_test_episode_file()
        teardown_test_show_dir()


class TestDBConnection(db.DBConnection, object):

    def __init__(self, db_file_name=TESTDBNAME, row_type=None):
        db_file_name = os.path.join(TESTDIR, db_file_name)
        super(TestDBConnection, self).__init__(db_file_name, row_type=row_type)


class TestCacheDBConnection(TestDBConnection, object):

    def __init__(self, provider_name):
        db.DBConnection.__init__(self, os.path.join(TESTDIR, TESTCACHEDBNAME))

        # Create the table if it's not already there
        try:
            sql = 'CREATE TABLE ' + provider_name + \
                  ' (name TEXT, season NUMERIC, episodes TEXT,' \
                  ' indexerid NUMERIC, url TEXT, time NUMERIC, quality TEXT);'
            self.connection.execute(sql)
            self.connection.commit()
        except sqlite3.OperationalError as e:
            if 'table %s already exists' % provider_name != str(e):
                raise

        # Create the table if it's not already there
        try:
            sql = 'CREATE TABLE lastUpdate (provider TEXT, time NUMERIC);'
            self.connection.execute(sql)
            self.connection.commit()
        except sqlite3.OperationalError as e:
            if 'table lastUpdate already exists' != str(e):
                raise


# this will override the normal db connection
sickgear.db.DBConnection = TestDBConnection
sickgear.tvcache.CacheDBConnection = TestCacheDBConnection


# =================
# test functions
# =================
def setup_test_db():
    """upgrades the db to the latest version
    """
    # upgrading the db
    db.migration_code(db.DBConnection())

    # fix up any db problems
    db.sanity_check_db(db.DBConnection(), mainDB.MainSanityCheck)

    # and for cachedb too
    db.upgrade_database(db.DBConnection('cache.db'), cache_db.InitialSchema)

    # and for faileddb too
    db.upgrade_database(db.DBConnection('failed.db'), failed_db.InitialSchema)


def teardown_test_db():
    """Deletes the test db
        although this seams not to work on my system it leaves me with an zero kb file
    """
    # uncomment next line so leave the db intact between test and at the end
    # return False
    try:
        sickgear.db.DBConnection().close()
    except (BaseException, Exception):
        pass
    try:
        sickgear.tvcache.CacheDBConnection().close()
    except (BaseException, Exception):
        pass

    # force python to garbage collect all db connections, so that the file can be deleted
    try:
        gc.collect(2)
    except (BaseException, Exception):
        pass

    for filename in glob.glob(os.path.join(TESTDIR, TESTDBNAME) + '*'):
        try:
            os.remove(filename)
        except (BaseException, Exception):
            pass
    for filename in glob.glob(os.path.join(TESTDIR, TESTCACHEDBNAME) + '*'):
        try:
            os.remove(filename)
        except (BaseException, Exception):
            pass
    for filename in glob.glob(os.path.join(TESTDIR, TESTFAILEDDBNAME) + '*'):
        try:
            os.remove(filename)
        except (BaseException, Exception):
            pass


def setup_test_episode_file():
    if not os.path.exists(FILEDIR):
        os.makedirs(FILEDIR)

    try:
        with open(FILEPATH, 'w') as f:
            f.write('foo bar')
    except EnvironmentError:
        print('Unable to set up test episode')
        raise


def teardown_test_episode_file():
    if os.path.exists(FILEDIR):
        shutil.rmtree(FILEDIR)


def setup_test_show_dir():
    if not os.path.exists(SHOWDIR):
        os.makedirs(SHOWDIR)


def teardown_test_show_dir():
    if os.path.exists(SHOWDIR):
        shutil.rmtree(SHOWDIR)


teardown_test_db()

if '__main__' == __name__:
    print('=========================')
    print('Dont call this directly')
    print('=========================')
    print('you might want to call')

    dirList = os.listdir(TESTDIR)
    for fname in dirList:
        if (0 < fname.find('_test')) and (0 > fname.find('pyc')):
            print('- ' + fname)

    print('=========================')
    print('or just call all_tests.py')
