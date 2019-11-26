#!/usr/bin/env python
# encoding: utf-8
#
# This file is part of ckanext-map
# Created by the Natural History Museum in London, UK

import nose
from mock import patch
from nose.tools import assert_equal, assert_raises, assert_true
from pylons import config
from sqlalchemy import MetaData, Table, create_engine, func
from sqlalchemy.sql import select

from ckan import model
from ckan.lib.create_test_data import CreateTestData
from ckan.plugins import toolkit
from ckan.tests import helpers, legacy


class TestViewCreated(helpers.FunctionalTestBase):
    '''These test cases check that tiled map views are created as expected,
    with appropriate default behaviour, and that the geometry columns are created as
    expected, with appropriate error messages. Note that the actions that create the
    geometry columns are fully tested elsewhere.
    '''
    context = None
    engine = None
    _load_plugins = [u'tiledmap', u'datastore']

    @classmethod
    def setup_class(cls):
        '''Prepare the test'''
        # We need datastore for these tests.
        if not legacy.is_datastore_supported():
            raise nose.SkipTest(u'Datastore not supported')

        super(TestViewCreated, cls).setup_class()

        CreateTestData.create()
        cls.context = {
            u'user': model.User.get(u'testsysadmin').name
            }
        cls.engine = create_engine(config[u'ckan.datastore.write_url'])

    def setup(self):
        '''Prepare each test'''
        package_create = toolkit.get_action('package_create')
        datastore_create = toolkit.get_action('datastore_create')
        datastore_upsert = toolkit.get_action('datastore_upsert')

        # Setup a dummy datastore.
        self.dataset = package_create(TestViewCreated.context, {
            u'name': u'map-test-dataset'
            })
        self.resource = datastore_create(TestViewCreated.context, {
            u'resource': {
                u'package_id': self.dataset[u'id']
                },
            u'fields': [
                {
                    u'id': u'id',
                    u'type': u'integer'
                    },
                {
                    u'id': u'latitude',
                    u'type': u'double precision'
                    },
                {
                    u'id': u'longitude',
                    u'type': u'double precision'
                    },
                {
                    u'id': u'long2',
                    u'type': u'double precision'
                    },
                {
                    u'id': u'text',
                    u'type': u'text'
                    },
                {
                    u'id': u'big',
                    u'type': u'double precision'
                    },
                ],
            u'primary_key': u'id'
            })

        # Add some data.
        datastore_upsert(TestViewCreated.context, {
            u'resource_id': self.resource[u'resource_id'],
            u'method': u'upsert',
            u'records': [{
                u'id': 1,
                u'latitude': -11,
                u'longitude': -15,
                u'long2': 22,
                u'text': u'hello',
                u'big': u'-1000'
                }, {
                u'id': 2,
                u'latitude': 23,
                u'longitude': 48,
                u'long2': -12,
                u'text': u'hello',
                u'big': u'199'
                }]
            })

        # Base dict for view creation/update methods
        self.base_data_dict = {
            u'description': u'',
            u'title': u'test',
            u'resource_id': self.resource[u'resource_id'],
            u'plot_marker_color': u'#EE0000',
            u'enable_plot_map': u'True',
            u'overlapping_records_view': u'',
            u'longitude_field': u'longitude',
            u'heat_intensity': u'0.1',
            u'view_type': u'tiledmap',
            u'utf_grid_title': u'_id',
            u'plot_marker_line_color': u'#FFFFFF',
            u'latitude_field': u'latitude',
            u'enable_utf_grid': u'True',
            u'grid_base_color': u'#F02323'
            }

    def teardown(self):
        '''Clean up after each test'''
        datastore_delete = toolkit.get_action('datastore_delete')
        package_delete = toolkit.get_action('package_delete')

        datastore_delete(TestViewCreated.context, {
            u'resource_id': self.resource[u'resource_id']
            })
        package_delete(TestViewCreated.context, {
            u'id': self.dataset[u'id']
            })

    @patch(u'ckan.lib.helpers.flash')
    def test_create_view_action_success(self, flash_mock):
        '''Test the create view action directly. Ensure that all values validate when
        correct.

        :param flash_mock: 

        '''
        resource_view_create = toolkit.get_action(u'resource_view_create')
        data_dict = dict(self.base_data_dict.items())
        resource_view = resource_view_create(TestViewCreated.context, data_dict)
        # Check we have lat/long values. This is done more extensively in test_actions.
        metadata = MetaData()
        table = Table(self.resource[u'resource_id'], metadata, autoload=True,
                      autoload_with=TestViewCreated.engine)
        s = select([
            table.c[u'latitude'],
            table.c[u'longitude'],
            func.st_x(table.c[u'_geom']).label(u'x'),
            func.st_y(table.c[u'_geom']).label(u'y'),
            ]).where(table.c[u'_the_geom_webmercator'] != None)
        r = TestViewCreated.engine.execute(s)
        try:
            assert_equal(r.rowcount, 2)
            for row in r:
                assert_equal(float(row[u'x']), float(row[u'longitude']))
                assert_equal(float(row[u'y']), float(row[u'latitude']))
        except:
            raise
        finally:
            r.close()
        # Check we have a message to inform us all went well
        assert_true(flash_mock.called)
        assert_equal(flash_mock.call_args[1][u'category'], u'alert-success')

    @patch(u'ckan.lib.helpers.flash')
    def test_create_view_action_failure(self, flash_mock):
        '''Test the create view action directly (failure test)

        :param flash_mock: 

        '''
        resource_view_create = toolkit.get_action(u'resource_view_create')
        # Check latitude must be numeric
        data_dict = dict(self.base_data_dict.items() + {
            u'title': u'test_la_n',
            u'latitude_field': u'text'
            }.items())
        with assert_raises(toolkit.ValidationError):
            resource_view = resource_view_create(TestViewCreated.context, data_dict)
        # Check latitude must be within range
        data_dict = dict(self.base_data_dict.items() + {
            u'title': u'test_la_r',
            u'latitude_field': u'big'
            }.items())
        with assert_raises(toolkit.ValidationError):
            resource_view = resource_view_create(TestViewCreated.context, data_dict)
        # Check longitude must be numeric
        data_dict = dict(self.base_data_dict.items() + {
            u'title': u'test_lo_n',
            u'longitude_field': u'text'
            }.items())
        with assert_raises(toolkit.ValidationError):
            resource_view = resource_view_create(TestViewCreated.context, data_dict)
        # Check longitude must be within range
        data_dict = dict(self.base_data_dict.items() + {
            u'title': u'test_lo_r',
            u'longitude_field': u'big'
            }.items())
        with assert_raises(toolkit.ValidationError):
            resource_view = resource_view_create(TestViewCreated.context, data_dict)
        # Check heat map intensity must be between 0 and 1
        data_dict = dict(self.base_data_dict.items() + {
            u'title': u'test_h',
            u'heat_intensity': u'2'
            }.items())
        with assert_raises(toolkit.ValidationError):
            resource_view = resource_view_create(TestViewCreated.context, data_dict)
        # Check color validation
        data_dict = dict(self.base_data_dict.items() + {
            u'title': u'test_c',
            u'plot_marker_color': u'carrot'
            }.items())
        with assert_raises(toolkit.ValidationError):
            resource_view = resource_view_create(TestViewCreated.context, data_dict)
        # Check field validation
        data_dict = dict(self.base_data_dict.items() + {
            u'title': u'test_f',
            u'utf_grid_title': u'carrot'
            }.items())
        with assert_raises(toolkit.ValidationError):
            resource_view = resource_view_create(TestViewCreated.context, data_dict)

    @patch(u'ckan.lib.helpers.flash')
    def test_update_view_action_success(self, flash_mock):
        '''Test the create view action directly (successfull test)

        :param flash_mock: 

        '''
        resource_view_create = toolkit.get_action(u'resource_view_create')
        resource_view_update = toolkit.get_action(u'resource_view_update')
        # First create a resource
        data_dict = dict(self.base_data_dict.items() + {
            u'title': u'test4'
            }.items())
        resource_view = resource_view_create(TestViewCreated.context, data_dict)
        # Now try to update it!
        data_dict[u'id'] = resource_view[u'id']
        data_dict[u'longitude_field'] = u'long2'
        resource_view_update(TestViewCreated.context, data_dict)
        # Check we have lat/long values. This is done more extensively in test_actions.
        metadata = MetaData()
        table = Table(self.resource[u'resource_id'], metadata, autoload=True,
                      autoload_with=TestViewCreated.engine)
        s = select([
            table.c[u'latitude'],
            table.c[u'long2'],
            func.st_x(table.c[u'_geom']).label(u'x'),
            func.st_y(table.c[u'_geom']).label(u'y'),
            ]).where(table.c[u'_the_geom_webmercator'] != None)
        r = TestViewCreated.engine.execute(s)
        try:
            assert_equal(r.rowcount, 2)
            for row in r:
                assert_equal(float(row[u'x']), float(row[u'long2']))
                assert_equal(float(row[u'y']), float(row[u'latitude']))
        except:
            raise
        finally:
            r.close()
        # Check we have a message to inform us all went well
        assert_true(flash_mock.called)
        assert_equal(flash_mock.call_args[1][u'category'], u'alert-success')

    @patch(u'ckan.lib.helpers.flash')
    def test_update_view_action_failure(self, flash_mock):
        '''Test the create view action directly (failure test)

        :param flash_mock: 

        '''
        resource_view_create = toolkit.get_action(u'resource_view_create')
        resource_view_update = toolkit.get_action(u'resource_view_update')
        # First create a resource
        data_dict = dict(self.base_data_dict.items() + {
            u'title': u'test4224'
            }.items())
        resource_view = resource_view_create(TestViewCreated.context, data_dict)
        data_dict[u'id'] = resource_view[u'id']
        # Now test an update - Check latitude must be numeric
        data_dict[u'latitude_field'] = u'text'
        with assert_raises(toolkit.ValidationError):
            resource_view_update(TestViewCreated.context, data_dict)
        # Check latitude must be within range
        data_dict[u'latitude_field'] = u'big'
        with assert_raises(toolkit.ValidationError):
            resource_view = resource_view_update(TestViewCreated.context, data_dict)
        # Check longitude must be numeric
        data_dict[u'latitude_field'] = u'latitude'
        data_dict[u'longitude_field'] = u'text'
        with assert_raises(toolkit.ValidationError):
            resource_view = resource_view_update(TestViewCreated.context, data_dict)
        # Check longitude must be within range
        data_dict[u'longitude_field'] = u'big'
        with assert_raises(toolkit.ValidationError):
            resource_view = resource_view_update(TestViewCreated.context, data_dict)
        # Check heat map intensity must be between 0 and 1
        data_dict[u'longitude_field'] = u'longitude'
        data_dict[u'heat_intensity'] = 2
        with assert_raises(toolkit.ValidationError):
            resource_view = resource_view_update(TestViewCreated.context, data_dict)
        # Check color validation
        data_dict[u'heat_intensity'] = 0.1
        data_dict[u'plot_marker_color'] = u'color'
        with assert_raises(toolkit.ValidationError):
            resource_view = resource_view_update(TestViewCreated.context, data_dict)
        # Check field validation
        data_dict[u'plot_marker_color'] = u'#FFFFFF'
        data_dict[u'utf_grid_title'] = u'carrot'
        with assert_raises(toolkit.ValidationError):
            resource_view = resource_view_update(TestViewCreated.context, data_dict)
        # To ensure we didn't mess up above, clean up and check it validates!
        data_dict[u'utf_grid_title'] = u'_id'
        resource_view = resource_view_update(TestViewCreated.context, data_dict)

    def test_delete_view_action(self):
        '''Test the delete view action directly'''
        # There is nothing to test because the action doesn't currently do anything.
        pass
