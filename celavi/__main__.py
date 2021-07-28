import argparse
import os
import pickle
from math import ceil
import matplotlib.pyplot as plt
from scipy.stats import weibull_min
import numpy as np
import pandas as pd
from celavi.routing import Router
from celavi.costgraph import CostGraph
from celavi.compute_locations import ComputeLocations

parser = argparse.ArgumentParser(description='Execute CELAVI model')
parser.add_argument('--data', help='Path to the input and output data folder.')
args = parser.parse_args()

# SUB FOLDERS
subfolder_dict = {}
# input data folder for pre-processed route data
subfolder_dict['preprocessing_output_folder'] = os.path.join(args.data, 'preprocessing/')
# input data folder for LCI
subfolder_dict['lci_folder'] = os.path.join(args.data, 'pylca_celavi_data')
# output folder for CELAVI results
subfolder_dict['outputs_folder'] = os.path.join(args.data, 'outputs')
# output folder for intermediate routing data
subfolder_dict['routing_output_folder'] = os.path.join(args.data, 'preprocessing', 'routing_intermediate_files/')

# check if directories exist, if not, create them
for folder in subfolder_dict.values():
    isdir = os.path.isdir(folder)
    if not isdir:
        os.makedirs(folder)

# FILE NAMES FOR INPUT DATA
# TODO: add check to ensure files exist
# general inputs
locations_filename = os.path.join(args.data, 'inputs', 'locations.csv')
locations_computed_filename = os.path.join(args.data, 'inputs', 'locations_computed.csv')
step_costs_filename = os.path.join(args.data, 'inputs', 'step_costs.csv')
fac_edges_filename = os.path.join(args.data, 'inputs', 'fac_edges.csv')
transpo_edges_filename = os.path.join(args.data, 'inputs', 'transpo_edges.csv')
route_pair_filename = os.path.join(args.data, 'inputs', 'route_pairs.csv')
avg_blade_masses_filename = os.path.join(args.data, 'inputs', 'avgblademass.csv')
routes_filename = os.path.join(args.data, 'preprocessing', 'routes.csv')
routes_computed_filename = os.path.join(args.data, 'preprocessing', 'routes_computed.csv')

# input file paths for precomputed US road network data
# transport graph (pre computed; don't change)
transportation_graph_filename = os.path.join(args.data, 'inputs',
                                             'precomputed_us_road_network',
                                             'transportation_graph.csv')

# node locations for transport graph (pre computed; don't change)
node_locations_filename = os.path.join(args.data, 'inputs',
                                       'precomputed_us_road_network',
                                       'node_locations.csv')

# file paths for raw data used to compute locations
wind_turbine_locations_filename = os.path.join(args.data, 'inputs',
                                               'raw_location_data',
                                               'uswtdb_v3_3_20210114.csv')
# LMOP data for landfill locations
landfill_locations_filename = os.path.join(args.data, 'inputs',
                                           'raw_location_data',
                                           'landfilllmopdata.csv')
# other facility locations (e.g., cement)
other_facility_locations_filename = os.path.join(args.data, 'inputs',
                                                 'raw_location_data',
                                                 'other_facility_locations_all_us.csv')

lookup_facility_type_filename = os.path.join(args.data, 'lookup_tables',
                                             'facility_type.csv')


# TODO: The tiny data and national data should use the same filename.
# When that is the case, place that filename below.
turbine_data_filename = os.path.join(args.data, 'inputs', 'number_of_turbines.csv')

# Because the LCIA code has filenames hardcoded and cannot be reconfigured,
# change the working directory to the lci_folder to accommodate those read
# and write operations. Also, the Context must be imported down here after
# the working directory is changed because the LCIA will attempt to read
# files immediately.

os.chdir(subfolder_dict['lci_folder'])
from celavi.des import Context

# if compute_locations is enabled (True), compute locations from raw input files (e.g., LMOP, US Wind Turbine Database)
compute_locations = False
use_computed_locations = True
# Note that the step_cost file must be updated (or programmatically generated)
# to include all facility ids. Otherwise, cost graph can't run with the full
# computed data set.
if compute_locations:
    loc = ComputeLocations(wind_turbine_locations=wind_turbine_locations_filename,
                           landfill_locations=landfill_locations_filename,
                           other_facility_locations=other_facility_locations_filename,
                           transportation_graph=transportation_graph_filename,
                           node_locations=node_locations_filename,
                           lookup_facility_type=lookup_facility_type_filename)
    loc.join_facilities(locations_output_file=locations_computed_filename)

if use_computed_locations:
    locations = locations_computed_filename
else:
    locations = locations_filename

# if run_routes is enabled (True), compute routing distances between all input locations
run_routes = False
if run_routes:
    routes_computed = Router.get_all_routes(locations_file=locations_filename,
                                            route_pair_file=route_pair_filename,
                                            transportation_graph=transportation_graph_filename,
                                            node_locations=node_locations_filename,
                                            routing_output_folder=subfolder_dict['routing_output_folder'],
                                            preprocessing_output_folder=subfolder_dict['preprocessing_output_folder'])
    # reset argument for routes file to use computed routes rather than user input
    args.routes = routes_computed_filename
else:
    routes = routes_filename


import time
time0 = time.time()
print('Cost Graph Startss\n\n\n')

netw = CostGraph(
    step_costs_file=step_costs_filename,
    fac_edges_file=fac_edges_filename,
    transpo_edges_file=transpo_edges_filename,
    locations_file=locations_filename,
    routes_file=routes_filename,
    sc_begin= 'in use',
    sc_end=['landfilling', 'cement co-processing'],
    year=2000.0,
    max_dist=300.0,
    verbose=1,
    blade_mass=50.0, #@todo update with actual value
    finegrind_cumul_initial=1.0,
    coarsegrind_cumul_initial=1.0,
    finegrind_initial_cost=80.0, #@todo update with actual value
    coarsegrind_initial_cost=60.0, #@todo update with actual value
    finegrind_learnrate=-0.05,
    coarsegrind_learnrate=-0.05
)


import pickle 
import math 
file_pi = open('netw_p_medium.obj', 'wb') 
pickle.dump(netw, file_pi)




print('Bypassing NETW Cost graph calculations',flush=True)
netw=pickle.load(open('netw_p_medium.obj', 'rb'))
print(str(time.time() - time0) + ' ' + 'taken for Cost Graph pickle reading',flush=True)




print(str(time.time() - time0) + ' ' + 'taken for Cost Graph run',flush=True)
print('Cost Graph Stops\n\n\n')
# Create the DES context and tie it to the CostGraph
context = Context(
    locations_filename=locations_filename,
    step_costs_filename=step_costs_filename,
    possible_items=["nacelle", "blade", "tower", "foundation"],
    cost_graph=netw,
    cost_graph_update_interval_timesteps=12,
    avg_blade_masses_filename=avg_blade_masses_filename
)

# Create the turbine dataframe that will be used to populate
# the context with components. Repeat the creation of blades
# 3 times for each turbine.

import time
time0 = time.time()
print('Reading turbine file\n\n\n',flush=True)


turbine_data = pd.read_csv(turbine_data_filename)
components = []
for _, row in turbine_data.iterrows():
    year = row['year']
    facility_id = int(row['facility_id'])
    n_turbine = int(row['n_turbine'])

    for _ in range(n_turbine):
        for _ in range(3):
            components.append({
                'year': year,
                'kind': 'blade',
                'facility_id': facility_id
            })


components = pd.DataFrame(components)

# Create the lifespan functions for the components.
np.random.seed(13)
timesteps_per_year = 12
min_lifespan = 120
L = 240
K = 2.2
lifespan_fns = {
    "nacelle": lambda: 30 * timesteps_per_year,
    "blade": lambda: 20 * timesteps_per_year,
    # "blade": lambda: weibull_min.rvs(K, loc=min_lifespan, scale=L-min_lifespan, size=1)[0],
    "foundation": lambda: 50 * timesteps_per_year,
    "tower": lambda: 50 * timesteps_per_year,
}


print(time0 - time.time())
print('TUrbine Stops\n\n\n',flush=True)


import time
time0 = time.time()
print('Components created\n\n\n',flush=True)

# Populate the context with components.
context.populate(components, lifespan_fns)

print(time0 - time.time())
print('Components Stops\n\n\n',flush=True)


import time
time0 = time.time()
print('Context created created\n\n\n',flush=True)


print('Run starting for DES\n\n\n',flush=True)
# Run the context
count_facility_inventories = context.run()

print(time0 - time.time())
print('FINISHED RUN',flush=True)

# Plot the cumulative count levels of the inventories
count_facility_inventory_items = list(count_facility_inventories.items())
nrows = 5
ncols = ceil(len(count_facility_inventory_items) / nrows)
fig, axs = plt.subplots(nrows=nrows, ncols=ncols, figsize=(10, 10))
plt.tight_layout()
for i in range(len(count_facility_inventory_items)):
    subplot_col = i // nrows
    subplot_row = i % nrows
    ax = axs[subplot_row][subplot_col]
    facility_name, facility = count_facility_inventory_items[i]
    cum_hist_blade = facility.cumulative_history["blade"]
    ax.set_title(facility_name)
    ax.plot(range(len(cum_hist_blade)), cum_hist_blade)
    ax.set_ylabel("tonnes")
plot_output_path = os.path.join(subfolder_dict['outputs_folder'], 'blade_counts.png')
plt.savefig(plot_output_path)
