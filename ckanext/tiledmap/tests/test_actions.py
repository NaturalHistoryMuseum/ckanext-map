#!/usr/bin/env python
# encoding: utf-8
#
# This file is part of ckanext-map
# Created by the Natural History Museum in London, UK

from pylons import config
import paste.fixture
import nose
from sqlalchemy import create_engine
from sqlalchemy.sql import select
from sqlalchemy import Table, MetaData, func
from sqlalchemy.engine import reflection

import ckan
import ckan.tests as tests
import ckan.plugins as p
import ckan.plugins.toolkit as toolkit
import ckan.config.middleware as middleware
import ckan.lib.create_test_data as ctd
from ckan.logic.action.create import package_create
from ckan.logic.action.delete import package_delete
from ckanext.datastore.logic.action import datastore_create, datastore_delete, datastore_upsert

from ckanext.tiledmap.config import config as tm_config


class TestMapActions(tests.WsgiAppCase):
    '''These test cases test the custom actions that are offered for creating the
    geometry columns ('create_geom_columns' and 'update_geom_columns')


    '''
    context = None
    engine = None

    @classmethod
    def setup_class(cls):
        '''Prepare the test'''
        # We need datastore for these tests.
        if not tests.is_datastore_supported():
            raise nose.SkipTest(u'Datastore not supported')

        # Setup a test app
        wsgiapp = middleware.make_app(config[u'global_conf'], **config)
        cls.app = paste.fixture.TestApp(wsgiapp)
        ctd.CreateTestData.create()
        cls.context = {u'model': ckan.model,
                       u'session': ckan.model.Session,
                       u'user': ckan.model.User.get(u'testsysadmin').name}
        cls.engine = create_engine(config[u'ckan.datastore.write_url'])

        # Load plugins
        p.load(u'tiledmap')
        p.load(u'datastore')

    @classmethod
    def teardown_class(cls):
        '''Clean up'''
        p.unload(u'tiledmap')
        p.unload(u'datastore')

    def setup(self):
        '''Prepare each test'''
        # Setup a dummy datastore.
        self.dataset = package_create(TestMapActions.context, {u'name': u'map-test-dataset'})
        self.resource = datastore_create(TestMapActions.context, {
            u'resource': {
                u'package_id': self.dataset[u'id']
            },
            u'fields': [
                {u'id': u'id', u'type': u'integer'},
                {u'id': u'latitude', u'type': u'double precision'},
                {u'id': u'longitude', u'type': u'double precision'},
                {u'id': u'skip', u'type': u'text'},
                {u'id': u'lat2', u'type': u'double precision'},
                {u'id': u'long2', u'type': u'double precision'}
            ],
            u'primary_key': u'id'
        })

        # Add some data.
        datastore_upsert(TestMapActions.context, {
            u'resource_id': self.resource[u'resource_id'],
            u'method': u'upsert',
            u'records': [{
                            u'id': 1,
                            u'latitude': -11,
                            u'longitude': -15,
                            u'skip': u'no',
                            u'lat2': 1,
                            u'long2': 1
                        }, {
                            u'id': 2,
                            u'latitude': 23,
                            u'longitude': 48,
                            u'skip': u'no',
                            u'lat2': 2,
                            u'long2': 2
                        }, {
                            u'id': 3,
                            u'latitude': None,
                            u'longitude': None,
                            u'skip': u'yes',
                            u'lat2': None,
                            u'long2': None
                        }, {
                            u'id': 4,
                            u'latitude': 1234,
                            u'longitude': 1234,
                            u'skip': u'yes',
                            u'lat2': None,
                            u'long2': None
                        }]
        })

    def teardown(self):
        '''Clean up after each test'''
        datastore_delete(TestMapActions.context, {u'resource_id': self.resource[u'resource_id']})
        package_delete(TestMapActions.context, {u'id': self.dataset[u'id']})
        tm_config.update({
            u'tiledmap.geom_field': u'_the_geom_webmercator',
            u'tiledmap.geom_field_4326': u'_geom'
        })

    def test_create_geom_columns(self):
        '''Test creating geom columns using default settings.'''
        # Create the geom columns
        create_geom_columns = toolkit.get_action(u'create_geom_columns')
        create_geom_columns(TestMapActions.context, {
            u'resource_id': self.resource[u'resource_id'],
            u'latitude_field': u'latitude',
            u'longitude_field': u'longitude'
        })
        # Test we have the expected columns
        metadata = MetaData()
        table = Table(self.resource[u'resource_id'], metadata, autoload=True, autoload_with=TestMapActions.engine)
        assert u'_geom' in table.c, u'Column geom was not created'
        assert u'_the_geom_webmercator' in table.c, u'Column _the_geom_webmercator was not created'
        s = select([
            table.c[u'latitude'],
            table.c[u'longitude'],
            func.st_x(table.c[u'_geom']).label(u'x'),
            func.st_y(table.c[u'_geom']).label(u'y'),
            table.c[u'skip']
        ]).where(table.c[u'_the_geom_webmercator'] != None)
        r = TestMapActions.engine.execute(s)
        try:
            assert r.rowcount == 2, u'Did not report the expected rows. Expecting {}, got {}'.format(2, r.rowcount)
            for row in r:
                assert float(row[u'x']) == float(row[u'longitude']), u'Longitude not correctly set'
                assert float(row[u'y']) == float(row[u'latitude']), u'Latitude not correctly set'
                assert row[u'skip'] == u'no', u'Row was included which should have not'
        except:
            raise
        finally:
            r.close()
        # Test we have the expected indices
        insp = reflection.Inspector.from_engine(TestMapActions.engine)
        index_exists = False

        for index in insp.get_indexes(self.resource[u'resource_id']):
            if ((self.resource[u'resource_id'] + u'__the_geom_webmercator_index').startswith(index[u'name'])
                and index[u'unique'] == False
                and len(index[u'column_names']) == 1
                and index[u'column_names'][0] == u'_the_geom_webmercator'):
                index_exists = True
                break
        assert index_exists, u'Index not created'

    def test_create_geom_columns_settings(self):
        '''Ensure settings are used if defined when creating columns'''
        tm_config[u'tiledmap.geom_field'] = u'alt_geom_webmercator'
        tm_config[u'tiledmap.geom_field_4326'] = u'alt_geom'
        # Test global settings override defaults
        create_geom_columns = toolkit.get_action(u'create_geom_columns')
        create_geom_columns(TestMapActions.context, {
            u'resource_id': self.resource[u'resource_id'],
            u'populate': False
        })
        # Test we have the expected columns
        metadata = MetaData()
        table = Table(self.resource[u'resource_id'], metadata, autoload=True, autoload_with=TestMapActions.engine)
        assert u'alt_geom' in table.c, u'Column alt_geom was not created'
        assert u'alt_geom_webmercator' in table.c, u'Column alt_geom_webmercator was not created'
        # Test we have the expected indices
        insp = reflection.Inspector.from_engine(TestMapActions.engine)
        index_exists = False
        for index in insp.get_indexes(self.resource[u'resource_id']):
            if ((self.resource[u'resource_id'] + u'_alt_geom_webmercator_index').startswith(index[u'name'])
                and index[u'unique'] == False
                and len(index[u'column_names']) == 1
                and index[u'column_names'][0] == u'alt_geom_webmercator'):
                index_exists = True
                break
        assert index_exists, u'Index not created'

    def test_populate(self):
        '''Ensure it's possible to first create the columns and populate/update them later'''
        create_geom_columns = toolkit.get_action(u'create_geom_columns')
        create_geom_columns(TestMapActions.context, {
            u'resource_id': self.resource[u'resource_id'],
            u'populate': False
        })
        # Test the result did not populate the geom field
        metadata = MetaData()
        table = Table(self.resource[u'resource_id'], metadata, autoload=True, autoload_with=TestMapActions.engine)
        s = select([u'*']).where(table.c[u'_the_geom_webmercator'] != None)
        r = TestMapActions.engine.execute(s)
        try:
            assert r.rowcount == 0, u'Table was populated'
        except:
            raise
        finally:
            r.close()

        # Now populate the entries, and test they are correct.
        update_geom_columns = toolkit.get_action(u'update_geom_columns')
        update_geom_columns(TestMapActions.context, {
            u'resource_id': self.resource[u'resource_id'],
            u'latitude_field': u'latitude',
            u'longitude_field': u'longitude'
        })
        metadata = MetaData()
        table = Table(self.resource[u'resource_id'], metadata, autoload=True, autoload_with=TestMapActions.engine)
        s = select([
            table.c[u'latitude'],
            table.c[u'longitude'],
            func.st_x(table.c[u'_geom']).label(u'x'),
            func.st_y(table.c[u'_geom']).label(u'y'),
            table.c[u'skip']
        ]).where(table.c[u'_the_geom_webmercator'] != None)
        r = TestMapActions.engine.execute(s)
        try:
            assert r.rowcount == 2, u'Did not report the expected rows. Expecting {}, got {}'.format(2, r.rowcount)
            for row in r:
                assert float(row[u'x']) == float(row[u'longitude']), u'Longitude not correctly set'
                assert float(row[u'y']) == float(row[u'latitude']), u'Latitude not correctly set'
                assert row[u'skip'] == u'no', u'Row was included which should have not'
        except:
            raise
        finally:
            r.close()
