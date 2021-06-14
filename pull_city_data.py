import numpy as np
import geopandas as gpd
import requests
import json
import os
from shapely import geometry
from bokeh.io import output_file, save
from bokeh.plotting import figure


def construct_grid(polygon, increment):
    sorted_lats = sorted(polygon.exterior.coords, key=lambda x: x[1])
    sorted_lons = sorted(polygon.exterior.coords, key=lambda x: x[0])

    min_lat, max_lat = sorted_lats[0][1], sorted_lats[-1][1]
    min_lon, max_lon = sorted_lons[0][0], sorted_lons[-1][0]

    point_grid = {
        'lats': [],
        'lons': []
    }

    for point_lat in np.arange(min_lat, max_lat, increment):
        for point_lon in np.arange(min_lon, max_lon, increment):
            point = geometry.Point(point_lon, point_lat)
            if polygon.contains(point):
                point_grid['lats'].append(point_lat)
                point_grid['lons'].append(point_lon)

    return point_grid


def define_city_geometry(city, state):
    state_df = gpd.read_file('data/shape_data/{0}/{0}.shp'.format(state))
    city_df = state_df[state_df['NAME'] == city]

    city_geometry = city_df.iloc[0]['geometry']

    if city == 'San Francisco':
        city_geometry = city_geometry[3]

    return city_geometry


def polygon2patch(city_geometry):
    geometry_data = {
        'xs': [],
        'ys': []
    }

    if isinstance(city_geometry, geometry.Polygon):
        geometry_data['xs'].append([point[0] for point in city_geometry.exterior.coords])
        geometry_data['ys'].append([point[1] for point in city_geometry.exterior.coords])
        for ring in city_geometry.interiors:
            geometry_data['xs'].append([point[0] for point in ring.coords])
            geometry_data['ys'].append([point[1] for point in ring.coords])
    else:
        for polygon in city_geometry:
            geometry_data['xs'].append([point[0] for point in polygon.exterior.coords])
            geometry_data['ys'].append([point[1] for point in polygon.exterior.coords])
            for ring in polygon.interiors:
                geometry_data['xs'].append([point[0] for point in ring.coords])
                geometry_data['ys'].append([point[1] for point in ring.coords])

    return geometry_data


def plot_init_grid(city, state, f_out):
    default_increment = 0.01
    city_geometry = define_city_geometry(city, state)
    if isinstance(city_geometry, geometry.Polygon):
        city_grid = construct_grid(city_geometry, default_increment)
    else:
        city_grid = {
            'lats': [],
            'lons': []
        }
        for poly in city_geometry:
            point_grid = construct_grid(poly, default_increment)
            city_grid['lats'].extend(point_grid['lats'])
            city_grid['lons'].extend(point_grid['lons'])

    polygon_points = polygon2patch(city_geometry)

    output_file(f_out)
    p = figure()
    p.circle('lons', 'lats', source=city_grid)
    p.multi_polygons(xs=[[polygon_points['xs']]],
                     ys=[[polygon_points['ys']]],
                     alpha=0.5, color='green')

    save(p)
    return city_grid


def get_nearby_venues(lat, lon, category_ids, client_secret, client_id, fsq_version, radius=500, limit=100):
    # Foursquare API url for venue queries
    base_url = "https://api.foursquare.com/v2/venues/explore"

    # Set up query parameters
    params = {'client_id': client_id, 'client_secret': client_secret, 'v': fsq_version,
              'll': str(lat) + ',' + str(lon), 'categoryId': ','.join(category_ids), 'radius': radius, 'limit': limit}

    query = requests.get(base_url, params=params)

    return query


def call_fsq(city, city_nickname, state, cat_names=None):
    if cat_names is None:
        cat_names = ['Fruit & Vegetable Store',
                     'Food & Drink Shop']

    with open('secrets/foursquare_secrets.json') as f_in:  # Load foursquare API credentials
        fsq_secrets = json.load(f_in)

    client_secret = fsq_secrets['CLIENT_SECRET']
    client_id = fsq_secrets['CLIENT_ID']
    fsq_version = '20180605'

    with open('variables/fsq_categories.json') as f_in:
        fsq_categories = json.load(f_in)

    init_grid_f_out = "plots/init_grid_{0}.html".format(city_nickname)
    city_grid = plot_init_grid(city, state, init_grid_f_out)

    venues_fname = "data/venues_results/{0}_venues_results.json".format(city_nickname)
    if os.path.isfile(venues_fname):
        with open(venues_fname) as f_in:
            city_venues_results = json.load(f_in)
    else:
        city_venues_results = []

    starting_index = len(city_venues_results)

    print("Making {0} Foursquare calls".format(len(city_grid['lats']) - starting_index))
    for i, (lat, lon) in enumerate(zip(city_grid['lats'], city_grid['lons'])):
        if i >= starting_index:
            query = get_nearby_venues(lat, lon, [fsq_categories[cat_name] for cat_name in cat_names],
                                      client_secret, client_id, fsq_version)
            if query.status_code != 200:
                print(i, query.status_code)
                break
            city_venues_results.append(query.json())

    with open(venues_fname, 'w') as f_out:
        json.dump(city_venues_results, f_out)

    return


if __name__ == '__main__':
    # call_fsq('Chicago', 'chicago', 'illinois')
    # call_fsq('San Francisco', 'sf', 'california')
    # call_fsq('New York', 'nyc', 'new_york')
    pass
