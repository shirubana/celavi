from typing import Dict, List, Callable

import simpy
import pandas as pd
import pysd  # type: ignore

from .inventory import Inventory
from .component import Component


class Context:
    """
    The Context class:

    - Provides the discrete time sequence for the model
    - Holds all the components in the model
    - Holds parameters for pathway cost models (dictionary)
    - Links the SD model to the DES model
    - Provides translation of years to timesteps and back again
    """

    def __init__(
        self,
        sd_model_filename: str = None,
        cost_params: Dict = None,
        min_year: int = 2000,
        max_timesteps: int = 600,
        years_per_timestep: float = 0.0833,
        learning_by_doing_timesteps: int = 1
    ):
        """
        Parameters
        ----------
        sd_model_filename: str
            Optional. If specified, it loads the PySD model in the given
            filename and writes it to a .csv in the current working
            directory. Also, it overrides min_year, max_timesteps,
            and years_per_timestep if specified.

        cost_params: Dict
            Dictionary of parameters for the learning-by-doing models and all
            other pathway cost models

        min_year: int
            The starting year of the model. Optional. If left unspecified
            defualts to 2000.

        max_timesteps: int
            The maximum number of discrete timesteps in the model. Defaults to
            200 or an end year of 2050.

        years_per_timestep: float
            The number of years covered by each timestep. Fractional
            values are allowed for timesteps that have a duration of
            less than one year. Default value is 0.25 or quarters (3 months).

        learning_by_doing_timesteps: int
            The number of timesteps that happen between each learning by
            doing recalculation.
        """

        if sd_model_filename is not None:
            self.sd_model_run = pysd.load(sd_model_filename).run()
            self.sd_model_run.to_csv("celavi_sd_model.csv")
            self.max_timesteps = len(self.sd_model_run)
            self.min_year = min(self.sd_model_run.loc[:, "TIME"])
            self.max_year = max(self.sd_model_run.loc[:, "TIME"])
            self.years_per_timestep = \
                (self.max_year - self.min_year) / len(self.sd_model_run)
        else:
            self.sd_model_run = None
            self.cost_params = cost_params
            self.max_timesteps = max_timesteps
            self.min_year = min_year
            self.years_per_timestep = years_per_timestep

        self.components: List[Component] = []
        self.env = simpy.Environment()

        # Inventories hold the simple counts of materials at stages of
        # their lifecycle. The "component" inventories hold the counts
        # of whole components. The "material" inventories hold the mass
        # of those components.

        self.landfill_component_inventory = Inventory(
            name="components in landfill",
            possible_items=["nacelle", "blade", "tower", "foundation",],
            timesteps=self.max_timesteps,
            quantity_unit="unit",
            can_be_negative=False,
        )

        self.use_component_inventory = Inventory(
            name="components in use",
            possible_items=["nacelle", "blade", "tower", "foundation",],
            timesteps=self.max_timesteps,
            quantity_unit="unit",
            can_be_negative=False,
        )

        # The virgin component inventory can go negative because it is
        # decremented every time a new component goes into service.

        self.virgin_component_inventory = Inventory(
            name="virgin components manufactured",
            possible_items=["nacelle", "blade", "tower", "foundation", ],
            timesteps=self.max_timesteps,
            quantity_unit="unit",
            can_be_negative=True,
        )

        self.recycle_to_raw_component_inventory = Inventory(
            name="components that have been recycled to a raw material",
            possible_items=["nacelle", "blade", "tower", "foundation", ],
            timesteps=self.max_timesteps,
            quantity_unit="unit",
            can_be_negative=False,
        )

        self.recycle_to_clinker_component_inventory = Inventory(
            name="components that have been recycled to clinker",
            possible_items=["nacelle", "blade", "tower", "foundation", ],
            timesteps=self.max_timesteps,
            quantity_unit="unit",
            can_be_negative=False,
        )

        self.landfill_material_inventory = Inventory(
            name="mass in landfill",
            possible_items=["nacelle", "blade", "tower", "foundation", ],
            timesteps=self.max_timesteps,
            quantity_unit="tonne",
            can_be_negative=False,
        )

        self.use_mass_inventory = Inventory(
            name="mass in use",
            possible_items=["nacelle", "blade", "tower", "foundation", ],
            timesteps=self.max_timesteps,
            quantity_unit="tonne",
            can_be_negative=False,
        )

        self.recycle_to_raw_material_inventory = Inventory(
            name="mass that has been recycled to a raw material",
            possible_items=["nacelle", "blade", "tower", "foundation", ],
            timesteps=self.max_timesteps,
            quantity_unit="unit",
            can_be_negative=False,
        )

        self.recycle_to_clinker_material_inventory = Inventory(
            name="mass that has been recycled to clinker",
            possible_items=["nacelle", "blade", "tower", "foundation", ],
            timesteps=self.max_timesteps,
            quantity_unit="unit",
            can_be_negative=False,
        )

        # The virgin component inventory can go negative because it is
        # decremented every time newly manufactured material goes into
        # service.

        self.virgin_material_inventory = Inventory(
            name="virgin material manufactured",
            possible_items=["nacelle", "blade", "tower", "foundation", ],
            timesteps=self.max_timesteps,
            quantity_unit="unit",
            can_be_negative=True,
        )

        # initialize dictionary to hold pathway costs over time
        self.cost_history = {'year': [],
                             'landfilling cost': [],
                             'recycling to clinker cost': [],
                             'recycling to raw material cost': [],
                             'blade removal cost, per tonne': [],
                             'blade removal cost, per blade': [],
                             'blade mass, tonne': [],
                             'coarse grinding cost': [],
                             'fine grinding cost': [],
                             'segment transpo cost': [],
                             'landfill tipping fee': []}

        # initialize dictionary to hold transportation requirements
        self.transpo_eol = {'year': [],
                            'total eol transportation': []}

        # These are the costs from the learning by doing model
        self.learning_by_doing_costs = {
            "landfilling": 1.0,
            "recycle_to_clink_pathway": 2.0,
            "recycle_to_rawmat_pathway": 2.0
        }

        self.learning_by_doing_timesteps = learning_by_doing_timesteps

    def years_to_timesteps(self, year: float) -> int:
        """
        Converts years into the corresponding timestep number of the discrete
        event model.

        Parameters
        ----------
        year: float
            The year can have a fractional part. The result of the conversion
            is rounding to the nearest integer.

        Returns
        -------
        int
            The discrete timestep that corresponds to the year.
        """

        return int(year / self.years_per_timestep)

    def timesteps_to_years(self, timesteps: int) -> float:
        """
        Converts the discrete timestep to a year.

        Parameters
        ----------
        timesteps: int
            The discrete timestep number. Must be an integer.

        Returns
        -------
        float
            The year converted from the discrete timestep.
        """
        return self.years_per_timestep * timesteps + self.min_year

    def populate(self, df: pd.DataFrame, lifespan_fns: Dict[str, Callable[[], float]]):
        """
        Before a model can run, components must be loaded into it. This method
        loads components from a DataFrame, has the following columns which
        correspond to the attributes of a component object:

        kind: str
            The type of component as a string. It isn't called "type" because
            "type" is a keyword in Python.

        xlong: float
            The longitude of the component.

        xlat: float
            The latitude of the component.

        year: float
            The year the component goes into use.

        mass_tonnes: float
            The mass of the component in tonnes.

        Each component is placed into a process that will timeout when the
        component begins its useful life, as specified in year. From there,
        choices about the component's lifecycle are made as further processes
        time out and decisions are made at subsequent timesteps.

        Parameters
        ----------
        df: pd.DataFrame
            The DataFrame which has components specified in the columns
            listed above.

        lifespan_fns: lifespan_fns: Dict[str, Callable[[], float]]
            A dictionary with the kind of component as the key and a Callable
            (probably a lambda function) that takes no arguments and returns
            a float as the value. When called, the value should return a value
            sampled from a probability distribution that corresponds to a
            predicted lifespan of the component. The key is used to call the
            value in a way similar to the following: lifespan_fns[row["kind"]]()
        """

        for _, row in df.iterrows():
            component = Component(
                kind=row["kind"],
                xlong=row["xlong"],
                ylat=row["ylat"],
                year=row["year"],
                mass_tonnes=row["mass_tonnes"],
                context=self,
                lifespan_timesteps=lifespan_fns[row["kind"]](),
            )
            self.env.process(component.begin_life(self.env))
            self.components.append(component)


    def choose_transition(self, component, timestep: int) -> str:
        """
        This chooses the transition (pathway) for a component when it reaches
        end of life. Currently, this only models the linear pathway where
        components are landfilled at the end of life

        The timestep of the discrete sequence is used to query the SD model
        for the current costs of each pathway as given from the learning
        by doing model.

        Parameters
        ----------
        component: Component
            The component for which a pathway is being chosen.

        timestep: int
            The timestep at which the pathway is being chosen.

        Returns
        -------
        str
            The name of the transition to make. This is then passed to
            the state machine in the component to move into the next
            state as chosen here.
        """

        # If there is no SD model, just landfill everything.
        # if self.sd_model_run is None:
        #     if component.state == "use":
        #         return "landfilling"
        #     else:
        #         raise ValueError("Components must always be in the state use.")

        # Capacity of recycling plant will need to be accounted for here.
        # Keep a cumulative tally of how much has been put through the
        # recycling facility.
        #
        # Keep track of capacity utilization at each timestep.

        _out = None

        # for BLADES ONLY
        # if the landfilling pathway cost is strictly less than recycling to raw
        # material pathway cost, then landfill. If the recycling pathway cost is
        # strictly less than landfilling, then recycling. If the two costs are
        # equal, then use the recycled material strategic value to decide: a
        # strategic value of zero means landfill while a strictly positive
        # strategic value means recycle.
        if component.state == "use":
            if component.kind == 'blade' and self.timesteps_to_years(timestep) >= 2019.0:

                # (recycle_to_rawmat_pathway,
                #  recycle_to_clink_pathway,
                #  landfill_pathway) = self.learning_by_doing(component, timestep)

                recycle_to_rawmat_pathway = self.learning_by_doing_costs["recycle_to_rawmat_pathway"]
                recycle_to_clink_pathway = self.learning_by_doing_costs["recycle_to_clink_pathway"]
                landfill_pathway = self.learning_by_doing_costs["landfilling"]

                if min(landfill_pathway, recycle_to_clink_pathway,
                       recycle_to_rawmat_pathway) == landfill_pathway:
                    _out = "landfilling"
                elif min(landfill_pathway, recycle_to_clink_pathway,
                             recycle_to_rawmat_pathway) == recycle_to_clink_pathway:
                    _out = "recycling_to_clinker"
                else:
                    _out = "recycling_to_raw"
            elif component.kind == 'blade' and self.timesteps_to_years(timestep) <= 2020:
                # this just saves the cost history for the results; everything
                # still gets landfilled
                #self.learning_by_doing(component, timestep)

                _out = "landfilling"
            else:
                # all other components get landfilled
                _out = "landfilling"

            return _out

        else:
            raise ValueError("Components must always be in the state use.")

    def average_blade_mass_tonnes(self, timestep):
        """
        Compute the average blade mass in tonnes for every blade in this
        context.

        Parameters
        ----------
        timestep: int
            The timestep at which this calculation is happening

        Returns
        -------
        float
            The average mass of the blade in tonnes.
        """
        total_blade_mass_eol = 0.0
        total_blade_count_eol = 0

        # Calculate the total mass at EOL
        total_blade_mass_eol += self.recycle_to_raw_material_inventory.transactions[timestep]["blade"]
        total_blade_mass_eol += self.recycle_to_clinker_material_inventory.transactions[timestep]["blade"]
        total_blade_mass_eol += self.landfill_material_inventory.transactions[timestep]["blade"]

        # Calculate the total count at EOL
        total_blade_count_eol += self.recycle_to_raw_component_inventory.transactions[timestep]["blade"]
        total_blade_count_eol += self.recycle_to_clinker_component_inventory.transactions[timestep]["blade"]
        total_blade_count_eol += self.landfill_component_inventory.transactions[timestep]["blade"]

        # Return the average mass for all the blades.
        if total_blade_count_eol > 0:
            return total_blade_mass_eol / total_blade_count_eol
        else:
            return 1

    def learning_by_doing_process(self, env):
        """
        This method contains a SimPy process that runs the learning-by-doing
        model on a periodic basis.
        """
        while True:
            yield env.timeout(self.learning_by_doing_timesteps)
            avg_blade_mass = self.average_blade_mass_tonnes(env.now)
            print('at timestep ', env.now, ', average blade mass is ', avg_blade_mass, ' tonnes\n')
            # This is a workaround. Make the learning by doing pathway costs
            # tolerant of a 0 mass for blades retired.
            if avg_blade_mass > 0:
                self.learning_by_doing(env.now, avg_blade_mass)

    def run(self) -> Dict[str, pd.DataFrame]:
        """
        This method starts the discrete event simulation running.

        Returns
        -------
        Dict[str, pd.DataFrame]
            A dictionary of inventories mapped to their cumulative histories.
        """
        # Schedule learning by doing timesteps (this will happen after all
        # other events have been scheduled)
        self.env.process(self.learning_by_doing_process(self.env))

        self.env.run(until=int(self.max_timesteps))
        inventories = {
            "landfill_component_inventory": self.landfill_component_inventory.cumulative_history,
            "landfill_material_inventory": self.landfill_material_inventory.cumulative_history,
            "virgin_component_inventory": self.virgin_component_inventory.cumulative_history,
            "virgin_material_inventory": self.virgin_material_inventory.cumulative_history,
            "recycle_to_raw_component_inventory": self.recycle_to_raw_component_inventory.cumulative_history,
            "recycle_to_raw_material_inventory": self.recycle_to_raw_material_inventory.cumulative_history,
            "recycle_to_clinker_component_inventory": self.recycle_to_clinker_component_inventory.cumulative_history,
            "recycle_to_clinker_material_inventory": self.recycle_to_clinker_material_inventory.cumulative_history,
            "cost_history": self.cost_history,
            "transpo_eol": self.transpo_eol
        }
        return inventories