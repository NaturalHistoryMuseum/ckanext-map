from pylons import config
import ckan.plugins as p
from ckan.common import json
import ckan.plugins.toolkit as toolkit
import ckanext.map.logic.action as map_action
import ckanext.map.logic.auth as map_auth
from ckanext.map.lib.helpers import mustache_wrapper

import ckan.logic as logic
get_action = logic.get_action


class MapPlugin(p.SingletonPlugin):
    """Windshaft map plugin

    This plugin replaces the recline preview template to use a custom map engine.
    The plugin provides controller routes to server tiles and grid from the winsdhaft
    backend. See MapController for configuration options.
    """
    p.implements(p.IConfigurer)
    p.implements(p.IRoutes, inherit=True)
    p.implements(p.IActions)
    p.implements(p.IAuthFunctions)
    p.implements(p.ITemplateHelpers)
    p.implements(p.IResourceView, inherit=True)

    ## IConfigurer
    def update_config(self, config):
        """Add our template directories to the list of available templates"""
        p.toolkit.add_template_directory(config, 'theme/templates')
        p.toolkit.add_public_directory(config, 'theme/public')
        p.toolkit.add_resource('theme/public', 'map')

    ## IRoutes
    def before_map(self, map):
        """Add routes to our tile/grid serving functionality"""
        map.connect('/map-tile/{z}/{x}/{y}.png', controller='ckanext.map.controllers.map:MapController', action='tile')
        map.connect('/map-grid/{z}/{x}/{y}.grid.json', controller='ckanext.map.controllers.map:MapController', action='grid')
        map.connect('/map-info', controller='ckanext.map.controllers.map:MapController', action='map_info')

        return map

    ## IActions
    def get_actions(self):
        """Add actions for creating/updating geom columns and override resource create/update/delete actions"""
        return {
            'create_geom_columns': map_action.create_geom_columns,
            'update_geom_columns': map_action.update_geom_columns,
            'resource_view_create': map_action.resource_view_create,
            'resource_view_update': map_action.resource_view_update,
            'resource_view_delete': map_action.resource_view_delete
        }

    ## IAuthFunctions
    def get_auth_functions(self):
        """Add auth functions for access to geom column creation actions"""
        return {
            'create_geom_columns': map_auth.create_geom_columns,
            'update_geom_columns': map_auth.update_geom_columns
        }

    ## ITemplateHelpers
    def get_helpers(self):
        """Add a template helper for formating mustache templates server side"""
        return {
            'mustache': mustache_wrapper
        }

    ## IResourceView
    def info(self):
        """Return generic info about the plugin"""
        return {
            'name': 'tiled_map',
            'title': 'Tiled map',
            'schema': {
                'latitude_field': [self._is_datastore_field],
                'longitude_field': [self._is_datastore_field],
            },
            'icon': 'compass',
            'iframed': True,
            'preview_enabled': False,
            'full_page_edit': False
        }

    def view_template(self, context, data_dict):
        return 'tiled_map_view.html'

    def form_template(self, context, data_dict):
        return 'tiled_map_form.html'

    def can_view(self, data_dict):
        """Specificy which resources can be viewed by this plugin"""
        # Check that the Windshaft server is configured
        if ((config.get('map.windshaft.host', None) is None) or
           (config.get('map.windshaft.port', None) is None)):
            return False
        # Check that we have a datastore for this resource
        if data_dict['resource'].get('datastore_active'):
            return True
        return False

    def setup_template_variables(self, context, data_dict):
        """Setup variables available to templates"""
        datastore_fields = self._get_datastore_fields(data_dict['resource']['id'])
        return {
            'resource_json': json.dumps(data_dict['resource']),
            'resource_view_json': json.dumps(data_dict['resource_view']),
            'map_fields': [{'name': f, 'value': f} for f in datastore_fields]
        }

    def _is_datastore_field(self, key, data, errors, context):
        """Check that a field is indeed a datastore field"""
        if not data[key] in self._get_datastore_fields(context['resource'].id):
            raise p.toolkit.Invalid('"{0}" is not a valid parameter'.format(data[key]))

    def _get_datastore_fields(self, rid):
        if not hasattr(self, '_datastore_fields'):
            self._datastore_fields = {}
        if not (rid in self._datastore_fields):
            data = {'resource_id': rid, 'limit': 0}
            fields = toolkit.get_action('datastore_search')({}, data)['fields']
            self._datastore_fields[rid] = [f['id'] for f in fields]

        return self._datastore_fields[rid]