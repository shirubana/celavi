# CELAVI
A circular economy emphasizes the efficient use of all resources (e.g., materials, land, water). Despite anticipated overall benefits to society, the transition to a circular economy is likely to create regional differences in impacts. Current tools are unable to fully evaluate these potential externalities, which will be important for informing research prioritization and regional decision making. 

The Circular Economy Lifecycle Assessment and VIsualization (CELAVI) framework allows stakeholders to quantify and visualize potential regional and sectoral transfers of impacts that could result from transitioning to a circular economy, with particular focus on energy materials. The framework uses system dynamics to model material flows for multiple circular economy pathways and decisions are based on learning-by-doing and are implemented via cost and strategic value of different circular economy pathways. It uses network theory to track the spatial and sectoral flow of functional units across a graph and discrete event simulation to to step through time and evaluate lifecycle assessment data at each time step. The framework is designed to be flexible and scalable to accommodate multiple energy materials and multiple energy technologies. The primary goal of CELAVI is to help answer questions about how material flows and environmental and economic impacts of energy systems might change if the circularity of energy systems increases. 

## macOS and Windows

On macOS, use Terminal to type the commands. On Windows, use the Anaconda Prompt. To start typing the commands, you will need to use the `cd` command (which does the same thing on macOS and Windows) to navigate to the root of the cloned repository. Most of the commands work the same on macOS or Windows. Where they differ, this documentation will call those difference out.

# Setup

## Discrete Event Simulation

This repository contains the discrete event simulation (DES) portion of the model. 

## pyLCA

The life cycle assessment (LCA) portion of the model.

## Input data

All necessary input data as well as a set of raw results is available in the `frontiers-fy21` branch of the `celavi-data` GitHub repository. Additional details on the contents of the input data files are available in the README of that repo.

### Turbine mass flows

Wind turbine installation in Texas in number of turbines per year, with average values for turbine blade and foundation mass.

### Life cycle inventory

Material and energy inputs for each of the processes involved in the end-of-life wind turbine blade supply chain.

## Running the model

Executing `simple_model_suites.py` will run all scenarios discussed in the Frontiers article.

### Output files and contents

1. `inventories` contains mass flows throughout the supply chain. 
2. `cost-histories` contains pathway cost trends and individual process costs.

## Postprocessing to calculate environmental impacts

How pyLCA is run using CELAVI output

## Creating visualizations from output files

Jupyter notebook `CELAVI-Figures`