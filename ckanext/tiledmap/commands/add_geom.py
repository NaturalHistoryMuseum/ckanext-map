#!/usr/bin/env python
# encoding: utf-8
#
# This file is part of ckanext-map
# Created by the Natural History Museum in London, UK

import logging

import sqlalchemy
from sqlalchemy import func
from sqlalchemy.sql import select

from ckan.plugins import toolkit

log = logging.getLogger(u'ckan')


class AddGeomCommand(toolkit.CkanCommand):
    '''Commands:
        paster ckanextmap add-all-geoms -c /etc/ckan/default/development.ini
    
    Where:
        <config> = path to your ckan config file
    
    The commands should be run from the ckanext-map directory.

    '''

    summary = __doc__.split(u'\n')[0]
    usage = __doc__
    counter = 0

    def command(self):
        '''Parse command line arguments and call appropriate method.'''
        if not self.args or self.args[0] in [u'--help', u'-h', u'help']:
            print AddGeomCommand.__doc__
            return

        cmd = self.args[0]

        self.method = cmd.replace(u'-', u'_')

        # Need to call _load_config() before running
        self._load_config()

        if self.method.startswith(u'_'):
            log.error(u'Cannot call private command %s' % (self.method,))
            return

        # Set up API context
        user = toolkit.get_action(u'get_site_user')({
            u'ignore_auth': True
            }, {})
        self.context = {
            u'user': user[u'name'],
            u'extras_as_string': True
            }

        # Set up datastore DB engine
        self.datastore_db_engine = sqlalchemy.create_engine(
            toolkit.config[u'ckan.datastore.write_url'])

        # Try and call the method, if it exists
        if hasattr(self, self.method):
            getattr(self, self.method)()
        else:
            log.error(u'Command %s not recognized' % (self.method,))

    def add_all_geoms(self):
        ''' '''
        packages = toolkit.get_action(u'current_package_list_with_resources')(
            self.context, {})
        for package in packages:
            for resource in package[u'resources']:
                log.info(resource[u'id'])

                has_col = False
                inspector = sqlalchemy.inspect(self.datastore_db_engine)
                cols = inspector.get_columns(resource[u'id'])
                for col in cols:
                    if col[u'name'] == u'latitude':
                        has_col = True

                log.info(u'Has latitude column: ' + str(has_col))

                if has_col:
                    # We need to wrap things in a transaction, since SQLAlchemy thinks
                    # that all selects (including AddGeometryColumn) should be rolled
                    # back when the connection terminates.
                    connection = self.datastore_db_engine.connect()
                    trans = connection.begin()

                    # Use these to remove the columns, if you're doing development things
                    # connection.execute(sqlalchemy.text("select DropGeometryColumn('"
                    # + resource['id'] + "', 'geom')"))
                    # connection.execute(sqlalchemy.text("select DropGeometryColumn('"
                    # + resource['id'] + "', 'the_geom_webmercator')"))

                    # Add the two geometry columns - one in degrees (EPSG:4326) and one
                    # in spherical mercator metres (EPSG:3857)
                    # the_geom_webmercator is used for windshaft
                    s = select([func.AddGeometryColumn(u'public', resource[u'id'],
                                                       u'geom', 4326, u'POINT', 2)])
                    connection.execute(s)
                    s = select([func.AddGeometryColumn(u'public', resource[u'id'],
                                                       u'the_geom_webmercator', 3857,
                                                       u'POINT', 2)])
                    connection.execute(s)

                    # Create geometries from the latitude and longitude columns. Note
                    # the bits and pieces of data cleaning that are required!
                    # This could, in theory, be converted to SQLAlchemy commands but
                    # LIFEISTOOSHORT
                    s = sqlalchemy.text(u'update \"' + resource[
                        u'id'] + u"\" set geom = st_setsrid(st_makepoint("
                                 u"longitude::float8, latitude::float8), 4326) where "
                                 u"latitude is not null and latitude != '' and "
                                 u"latitude not like '%{%'")
                    connection.execute(s)
                    s = sqlalchemy.text(u'update \"' + resource[
                        u'id'] + u'\" set the_geom_webmercator = st_transform(geom, '
                                 u'3857) where y(geom) < 90 and y(geom) > -90')
                    connection.execute(s)

                    trans.commit()
