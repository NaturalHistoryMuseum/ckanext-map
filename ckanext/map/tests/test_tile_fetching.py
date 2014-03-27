import re
import urllib
import urlparse

from pylons import config
import paste.fixture
from sqlalchemy import create_engine
import nose
from mock import patch

import ckan
import ckan.tests as tests
import ckan.plugins as p
import ckan.config.middleware as middleware
import ckan.lib.create_test_data as ctd
from ckan.logic.action.create import package_create
from ckan.logic.action.delete import package_delete
from ckanext.datastore.logic.action import datastore_create, datastore_delete


class TestTileFetching(tests.WsgiAppCase):
    """Test cases for the Map plugin"""
    dataset = None
    resource = None
    context = None

    @classmethod
    def setup_class(cls):
        """Prepare the test"""
        # We need datastore for these tests.
        if not tests.is_datastore_supported():
            raise nose.SkipTest("Datastore not supported")

        # Setup a test app
        wsgiapp = middleware.make_app(config['global_conf'], **config)
        cls.app = paste.fixture.TestApp(wsgiapp)
        ctd.CreateTestData.create()
        cls.context = {'model': ckan.model,
                       'session': ckan.model.Session,
                       'user': ckan.model.User.get('testsysadmin').name}

        # Load plugins
        p.load('map')
        p.load('datastore')

        # Setup a dummy datastore ; the map plugin just needs the schema in order to build
        # the query it passes to windshaft, so no actual data is needed for these tests and
        # the type of the field is not important.
        cls.dataset = package_create(cls.context, {'name': 'map-test-dataset'})
        cls.resource = datastore_create(cls.context, {
            'resource': {
                'package_id': cls.dataset['id']
            },
            'fields': [
                {'id': 'the_geom_webmercator', 'type': 'text'},
                {'id': 'the_geom_2', 'type': 'text'},
                {'id': 'some_field_1', 'type': 'text'},
                {'id': 'some_field_2', 'type': 'text'}
            ]
        })

    @classmethod
    def teardown_class(cls):
        """Clean up after the test"""
        datastore_delete(cls.context, {'resource_id': cls.resource['resource_id']})
        package_delete(cls.context, {'id': cls.dataset['id']})
        p.unload('map')
        p.unload('datastore')

    def teardown(self):
        # Ensure all settings are reset to default.
        tod = ['map.windshaft.host', 'map.windshaft.port', 'map.windshaft.database', 'map.geom_field',
               'map.interactivity']
        for opt in tod:
            if config.get(opt, None) != None:
                del config[opt]

    @patch('urllib.urlopen')
    def test_fetch_tile_invoke(self, mock_urlopen):
        """Test that the map tile plugin invokes windshaft correctly

        This test ensures that:
        - The default windshaft host/port settings are used when no setting are specified;
        - The current datastore database is used;
        - The table provided as resource_id is used;
        - The requested tile coordinates are preserved
        """
        engine = create_engine(config['ckan.datastore.write_url'])
        windshaft_database = engine.url.database
        mock_urlopen.return_value.read.return_value = 'data from windshaft :-)'
        res = self.app.get('/map-tile/1/2/3.png?resource_id={}'.format(TestTileFetching.resource['resource_id']))
        # Ensure the mock urlopen was called
        assert mock_urlopen.called, 'urlopen was not called'
        assert mock_urlopen.return_value.read.called, 'read was not called'
        assert 'data from windshaft :-)' in res, 'map tile action did not return content'
        # Now check the URL that windshaft was called with
        called_url = urlparse.urlparse(mock_urlopen.call_args[0][0])
        called_query = urlparse.parse_qs(called_url.query)
        assert called_url.netloc == '127.0.0.1:4000', '''Map tile plugin did not use default values for
                                                         Windshaft settings'''
        assert 'database/{}/'.format(windshaft_database) in called_url.path, '''Map tile plugin did not use engine
                                                                           database'''
        assert 'table/{}/'.format(TestTileFetching.resource['resource_id']) in called_url.path, '''Map tile plugin did
                                                                                              not use provided
                                                                                              resource id'''
        assert '/1/2/3.png' in called_url.path, 'Map tile plugin did not use correct coordinates'

    @patch('urllib.urlopen')
    def test_fetch_tile_settings(self, mock_urlopen):
        """Test that configuration settings are used if present"""
        config['map.windshaft.host'] = 'example.com'
        config['map.windshaft.port'] = '1234'
        config['map.windshaft.database'] = 'wdb'
        config['map.geom_field'] = 'the_geom_2'
        config['map.interactivity'] = 'some_field_1,some_field_2'
        mock_urlopen.return_value.read.return_value = 'data from windshaft :-)'
        self.app.get('/map-tile/2/3/4.png?resource_id={}'.format(TestTileFetching.resource['resource_id']))
        # Now check the URL that windshaft was called with
        assert mock_urlopen.return_value.read.called, 'url open was not called'
        called_url = urlparse.urlparse(mock_urlopen.call_args[0][0])
        called_query = urlparse.parse_qs(called_url.query)
        assert called_url.netloc == 'example.com:1234' in called_url, '''Map tile plugin did not use config windshaft
                                                                        values'''
        assert 'database/wdb/' in called_url.path, '''Map tile plugin did not use config windshaft values'''
        assert 'the_geom_2'in called_query['sql'][0], '''Map tile plugin did not use geom_field configuration option'''
        # Also check that interactivity fields are added
        mock_urlopen.return_value.read.reset_mock()
        mock_urlopen.reset_mock()
        mock_urlopen.return_value.read.return_value = 'data from windshaft :-)'
        self.app.get('/map-grid/2/3/4.grid.json?resource_id={}'.format(TestTileFetching.resource['resource_id']))
        called_url = urlparse.urlparse(mock_urlopen.call_args[0][0])
        called_query = urlparse.parse_qs(called_url.query)
        assert 'some_field_1' in called_query['sql'][0] and 'some_field_2' in called_query['sql'][0], '''Grid tile not including
                                                                                             defined interactivity'''

    @patch('urllib.urlopen')
    def test_fetch_tile_sql_plain(self, mock_urlopen):
        """Test the SQL query sent to windshaft is correct (no filters/geometry, tile only)"""
        mock_urlopen.return_value.read.return_value = 'data from windshaft :-)'
        self.app.get('/map-tile/4/5/6.png?resource_id={}'.format(TestTileFetching.resource['resource_id']))
        # Now check the URL that windshaft was called with
        assert mock_urlopen.called, 'url open not called'
        called_url = urlparse.urlparse(mock_urlopen.call_args[0][0])
        called_query = urlparse.parse_qs(called_url.query)
        sql = '''
          SELECT the_geom_webmercator
            FROM (SELECT DISTINCT ON (the_geom_webmercator) "{rid}".the_geom_webmercator AS the_geom_webmercator
                    FROM "{rid}") AS _mapplugin_sub ORDER BY random()
        '''.format(rid=TestTileFetching.resource['resource_id']).strip()
        assert re.sub('\s+', ' ', sql).strip() == re.sub('\s+', ' ', called_query['sql'][0]), '''Map tile plugin did not
                                          generate correct SQL : {} instead of {}'''.format(called_query['sql'][0], sql)

    @patch('urllib.urlopen')
    def test_fetch_tile_sql_param(self, mock_urlopen):
        """Test the SQL query sent to windshaft is correct (filters & geometry, tile only)"""
        mock_urlopen.return_value.read.return_value = 'data from windshaft :-)'
        filters = '[{"type":"term","field":"some_field_1","term":"value"}]'
        geom = 'POLYGON ((20.302734375 53.38332836757156, 31.376953125 56.75272287205736, 38.408203125 49.724479188713005, 27.59765625 48.748945343432936, 20.302734375 53.38332836757156))'
        self.app.get('/map-tile/4/5/6.png?resource_id={resource_id}&filters={filters}&geom={geom}'.format(
            resource_id=TestTileFetching.resource['resource_id'],
            filters=urllib.quote_plus(filters),
            geom=urllib.quote_plus(geom)
        ))
        # Now check the URL that windshaft was called with
        assert mock_urlopen.called, 'url open not called'
        called_url = urlparse.urlparse(mock_urlopen.call_args[0][0])
        called_query = urlparse.parse_qs(called_url.query)
        sql = '''
          SELECT the_geom_webmercator
          FROM (SELECT DISTINCT ON (the_geom_webmercator) "{rid}".the_geom_webmercator AS the_geom_webmercator
                FROM "{rid}"
                WHERE "{rid}".some_field_1 = 'value' AND
                ST_Intersects("{rid}".the_geom_webmercator, ST_Transform(ST_GeomFromText('POLYGON ((20.302734375 53.38332836757156, 31.376953125 56.75272287205736, 38.408203125 49.724479188713005, 27.59765625 48.748945343432936, 20.302734375 53.38332836757156))', 4326), 3857)))
                AS _mapplugin_sub ORDER BY random()
        '''.format(rid=TestTileFetching.resource['resource_id']).strip()
        assert re.sub('\s+', ' ', sql).strip() == re.sub('\s+', ' ', called_query['sql'][0]), '''Map tile plugin did not
                                          generate correct SQL : {} instead of {}'''.format(called_query['sql'][0], sql)