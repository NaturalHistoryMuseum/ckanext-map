// Integrating the NHM Map

this.recline = this.recline || {};
this.recline.View = this.recline.View || {};

(function($, my) {

my.NHMMap = Backbone.View.extend({
  className: 'recline-nhm-map well',
  template: '\
    <div class="recline-map"> \
      <div class="panel map"></div> \
    </div> \
  ',
  initialize: function() {
    this.el = $(this.el);
    _.bindAll(this, 'render');
    this.model.queryState.bind('change', this.render);
  },
  render: function() {

    var self = this;

    out = Mustache.render(this.template);
    $(this.el).html(out);
    this.$map = this.el.find('.panel.map');

//    if (!self.mapReady){
//      self._setupMap();
//    }

    self._setupMap();

    self.redraw();

//    var filters = {}
//
//    $.each(this.model.queryState.attributes.filters, function( i, filter ) {
//        filters[filter.field] = filter.term;
//    });
//
//    if (this.model.queryState.attributes.q){
//        filters['q'] = this.model.queryState.attributes.q
//    }

//    var tmplData = {}
//
//    var jqxhr = $.ajax({
//        url: '/map/' + this.model.id,
//        type: 'POST',
//        data: filters,
//        success: function(response) {
//            tmplData = response;
//        },
//        async: false
//    });
//
//    var out = Mustache.render(this.template, tmplData);
//    var out = Mustache.render(this.template);
//    this.el.html(out);

  },

  show: function() {
     $('.recline-pager').hide();

    /* If the div was hidden, Leaflet needs to recalculate some sizes to display properly */
    if (this.map){
      this.map.invalidateSize();
      if (this._zoomPending && this.state.get('autoZoom')) {
        this._zoomToFeatures();
        this._zoomPending = false;
      }
    }
    this.visible = true;
  },

  hide: function() {
     $('.recline-pager').show();
  },

  _setupMap: function(){
    var self = this;
    var resource_id = this.model.id

    this.map = new L.Map(this.$map.get(0));

    this.map.setView(new L.LatLng(51.505, -0.09), 4, true);
    L.tileLayer('http://otile1.mqcdn.com/tiles/1.0.0/map/{z}/{x}/{y}.jpg', { opacity: 0.8 }).addTo(this.map);

    var drawControl = new L.Control.Draw({
     draw: {
        polyline: false,
        marker: false,
        circle: false
      }
    });
    this.map.addControl(drawControl);
    this.drawLayer = null;

    this.tilejson = {
            tilejson: '1.0.0',
            scheme: 'xyz',
            tiles: [],
            grids: [],
            formatter: function(options, data) { return data._id + "/" + data.species + "/" + data.scientific_name }
    };

    this.map.on('draw:created', function (e) {
      var type = e.layerType;
      var layer = e.layer;
      if (self.drawLayer) {
        self.map.removeLayer(self.drawLayer);
      }
      self.map.addLayer(layer);
      self.drawLayer = layer;
      self.redraw();
    });

    this.tiles_url = '/map-tile/{z}/{x}/{y}.png';
    this.grids_url = '/map-grid/{z}/{x}/{y}.grid.json?callback={cb}';

    this.info = L.control();
    this.info.options.position = 'bottomright';

    this.info.onAdd = function (map) {
      this._div = L.DomUtil.create('div', 'info'); // create a div with a class "info"
      this.update();
      return this._div;
    };

    this.info.update = function (props) {
      var template;
      if (props) {
        template = [
          '<h4>' + self.model.attributes.name + ' Records</h4>',
          '<b>{{ data.species }}</b><br />',
          '{{ data._id }}<br />',
          '{{ data.scientific_name }}<br/>',
          '{{ data.count }} records overlapping'
        ].join('');
      } else {
        template = [
          '<h4>' + self.model.attributes.name + ' Records</h4>',
          '<p>Hover over a marker</p>'
        ].join('');
      }
      this._div.innerHTML = Mustache.render(template, props);
    };

    this.layers = [];
    this.controls = [];
    this.mapReady = true;

  },

  redraw: function(){

    var self = this;
    var params = {};

    params['filters'] = JSON.stringify(this.model.queryState.attributes.filters);

    if (this.model.queryState.attributes.q){
      params['q'] = this.model.queryState.attributes.q;
    }

    if (this.drawLayer) {
      var geojson = this.drawLayer.toGeoJSON();
      params['geom'] = Terraformer.WKT.convert(geojson.geometry);
    }

    params['resource_id'] = this.model.id;

    this.tilejson.tiles = [this.tiles_url + "?" + $.param(params)];
    this.tilejson.grids = [this.grids_url + "&" + $.param(params)];

    _.each(this.layers, function(layer){
        self.map.removeLayer(layer)
    });

    _.each(this.controls, function(control) {
        self.map.removeControl(control)
    });

    this.layers = [];
    this.controls = [];

    var testMap = L.tileLayer(this.tilejson.tiles[0]).addTo(this.map);
    var utfGrid = new L.UtfGrid(this.tilejson.grids[0], {
      resolution: 4
    });

    utfGrid.on('mouseover', function(e){ self.info.update(e);}).on('mouseout', function(e){ self.info.update();})
    this.map.addLayer(utfGrid);
    this.map.addControl(this.info);

    this.controls.push(this.info);
    this.layers.push(utfGrid);
    this.layers.push(testMap);

  }


});

})(jQuery, recline.View);