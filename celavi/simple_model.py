from typing import Dict, List, Callable

import simpy
import pandas as pd
import numpy as np
import pysd  # type: ignore
import os

from .unique_identifier import UniqueIdentifier
from .states import StateTransition, NextState
from .inventory import Inventory

import pdb
class Component:
    """
    This class models a component in the discrete event simulation (DES) model.

    transitions_table: Dict[StateTransition, NextState]
        The transition table for the state machine. E.g., when a component
        begins life, it enters the "use" state. When a component is in the
        "use" state, it can receive the transition "landfilling", which
        transitions the component into the "landfill" state.
    """

    def __init__(
        self,
        context,
        kind: str,
        xlong: float,
        ylat: float,
        year: int,
        lifespan_timesteps: float,
        mass_tonnes: float,
    ):
        """
        This takes parameters named the same as the instance variables. See
        the comments for the class for further information about instance
        attributes.

        It sets the initial state, which is an empty string. This is
        because there is no state until the component begins life, when
        the process defined in method begin_life() is called by SimPy.

        Parameters
        ----------
        context: Context
            The context that contains this component.

        kind: str
            The type of this component. The word "type", however, is also a Python
            keyword, so this attribute is named kind.

        xlong: float
            The longitude of the component.

        xlat: float
            The latitude of the component.

        year: int
            The year in which this component enters the use state for the first
            time.

        lifespan_timesteps: float
            The lifespan, in timesteps, of the component. The argument can be
            provided as a floating point value, but it is converted into an
            integer before it is assigned to the instance attribute. This allows
            more intuitive integration with random number generators defined
            outside this class which may return floating point values.

        mass_tonnes: float
            The total mass of the component, in tonnes.
        """

        self.state = ""  # There is no state until beginning of life
        self.context = context
        self.id = UniqueIdentifier.unique_identifier()
        self.kind = kind
        self.xlong = xlong
        self.ylat = ylat
        self.year = year
        self.mass_tonnes = mass_tonnes
        self.lifespan_timesteps = int(lifespan_timesteps)  # timesteps
        self.transitions_table = self.make_transitions_table()
        self.transition_list: List[str] = []

    def make_transitions_table(self) -> Dict[StateTransition, NextState]:
        """
        This method should be called once during instantiation of a component.

        It creates the table of states, transitions, and next states.

        Both recycling and landfilling have long lifetimes. For an explanation
        of why, see their state entry functions.

        Returns
        -------
        Dict[StateTransition, NextState]
            A dictionary mapping current states and transitions (the key) into
            the next state (the value). See the documentation for the
            StateTransition and NextState classes.
        """
        transitions_table = {
            StateTransition(state="use", transition="landfilling"): NextState(
                state="landfill",
                lifespan_min=1000,
                lifespan_max=1000,
                state_entry_function=self.landfill,
                state_exit_function=self.leave_use,
            ),
            StateTransition(state="use", transition="recycling_to_raw"): NextState(
                state="recycle_to_raw",
                lifespan_min=1000,
                lifespan_max=1000,
                state_entry_function=self.recycle_to_raw,
                state_exit_function=self.leave_use,
            ),
            StateTransition(state="use", transition="recycling_to_clinker"): NextState(
                state="recycle_to_clinker",
                lifespan_min=1000,
                lifespan_max=1000,
                state_entry_function=self.recycle_to_clinker,
                state_exit_function=self.leave_use,
            )
        }

        return transitions_table

    @staticmethod
    def recycle_to_raw(context, component, timestep: int) -> None:
        """
        Recycles a component by incrementing the material in recycling storage.

        Currently, there is no corresponding leave_recycle because only other
        processes deduct from the recycling inventory (e.g., manufacturing)

        Parameters
        ----------
        context: Context
            The context in which this component lives. There is no type
            in the method signature to prevent a circular dependency.

        component: Component
            The component which is being landfilled.
        """
        context.recycle_to_raw_component_inventory.increment_quantity(
            item_name=component.kind, quantity=0.7, timestep=timestep
        )
        context.recycle_to_raw_mass_inventory.increment_quantity(
            item_name=component.kind, quantity=0.7*component.mass_tonnes, timestep=timestep
        )
        context.landfill_component_inventory.increment_quantity(
            item_name=component.kind, quantity=0.3, timestep=timestep
        )
        context.landfill_mass_inventory.increment_quantity(
            item_name=component.kind, quantity=0.3*component.mass_tonnes, timestep=timestep)

    @staticmethod
    def recycle_to_clinker(context, component, timestep: int) -> None:
        """
        Recycles a component to clinker by incrementing the material in
        recycling-to-clinker storage.

        Currently, there is no corresponding leave_recycle because only other
        processes deduct from the recycling inventory (e.g., manufacturing)

        Parameters
        ----------
        context: Context
            The context in which this component lives. There is no type
            in the method signature to prevent a circular dependency.

        component: Component
            The component which is being landfilled.
        """
        context.recycle_to_clinker_component_inventory.increment_quantity(
            item_name=component.kind, quantity=1, timestep=timestep
        )
        context.recycle_to_clinker_mass_inventory.increment_quantity(
            item_name=component.kind, quantity=component.mass_tonnes, timestep=timestep
        )

    @staticmethod
    def landfill(context, component, timestep: int) -> None:
        """
        Landfills a component by incrementing the material in the landfill.

        The landfill process is special because there is no corresponding
        leave_landfill method since component materials never leave the
        landfill.

        This is a static method so it can be called by an arbitrary function
        during a SimPy process. Since it is a static method, it is not
        attached to any instance of the Component class, so the component
        must be passed explicitly.

        Parameters
        ----------
        context: Context
            The context in which this component lives. There is no type
            in the method signature to prevent a circular dependency.

        component: Component
            The component which is being landfilled.
        """
        # print(f"Landfill process component {component.id}, kind {component.kind} timestep={timestep}")
        context.landfill_component_inventory.increment_quantity(
            item_name=component.kind, quantity=1, timestep=timestep,
        )
        context.landfill_mass_inventory.increment_quantity(
            item_name=component.kind, quantity=component.mass_tonnes, timestep=timestep,
        )

    @staticmethod
    def use(context, component, timestep: int) -> None:
        """
        Makes a material enter the use phases from another state.

        This is a static method so it can be called by an arbitrary function
        during a SimPy process. Since it is a static method, it is not
        attached to any instance of the Component class, so the component
        must be passed explicitly.

        Parameters
        ----------
        context: Context
            The context in which this component lives. There is no type
            in the method signature to prevent a circular dependency.

        component: Component
            The component which is being landfilled.
        """
        # print(f"Use process component {component.id}, timestep={timestep}")
        context.use_component_inventory.increment_quantity(
            item_name=component.kind, quantity=1, timestep=timestep,
        )
        context.use_mass_inventory.increment_quantity(
            item_name=component.kind, quantity=component.mass_tonnes, timestep=timestep,
        )

        context.virgin_component_inventory.increment_quantity(
            item_name=component.kind, quantity=-1, timestep=timestep
        )
        context.virgin_material_inventory.increment_quantity(
            item_name=component.kind, quantity=-component.mass_tonnes,
            timestep=timestep,
        )



    @staticmethod
    def leave_use(context, component, timestep: int):
        """
        This method decrements the use inventory when a component material leaves use.

        This is a static method so it can be called by an arbitrary function
        during a SimPy process. Since it is a static method, it is not
        attached to any instance of the Component class, so the component
        must be passed explicitly.

        Parameters
        ----------
        context: Context
            The conext in which this component lives

        component: Component
            The component which is being taken out of use.
        """
        # print(
        #     f"Leave use process component_material {component.id}, timestep={timestep}"
        # )
        context.use_component_inventory.increment_quantity(
            item_name=component.kind, quantity=-1, timestep=timestep,
        )
        context.use_mass_inventory.increment_quantity(
            item_name=component.kind, quantity=-component.mass_tonnes, timestep=timestep,
        )

    def begin_life(self, env):
        """
        This process should be called exactly once during the discrete event
        simulation. It is what starts the lifetime this component. Since it is
        only called once, it does not have a loop, like most other SimPy
        processes. When the component enters life, this method immediately
        sets the end-of-life (EOL) process for the use state.

        Parameters
        ----------
        env: simpy.Environment
            The SimPy environment running the DES timesteps.
        """
        begin_timestep = (
            self.year - self.context.min_year
        ) / self.context.years_per_timestep
        yield env.timeout(begin_timestep)
        # print(
        #     f"yr: {self.year}, ts: {begin_timestep}. {self.kind} {self.id} beginning life."
        # )
        self.state = "use"
        self.transition_list.append("using")
        self.use(self.context, self, env.now)
        env.process(self.eol_process(env))

    def transition(self, transition: str, timestep: int) -> None:
        """
        Transition the component's state machine from the current state based on a
        transition.

        Parameters
        ----------
        transition: str
            The next state to transition into.

        timestep: int
            The discrete timestep.

        Returns
        -------
        None

        Raises
        ------
        KeyError
            Raises a KeyError if the transition is not accessible from the
            current state.
        """
        lookup = StateTransition(state=self.state, transition=transition)
        if lookup not in self.transitions_table:
            raise KeyError(
                f"transition: {transition} not allowed from current state {self.state}"
            )
        next_state = self.transitions_table[lookup]
        self.state = next_state.state
        self.lifespan_timesteps = next_state.lifespan
        self.transition_list.append(transition)
        if next_state.state_entry_function is not None:
            next_state.state_entry_function(self.context, self, timestep)
        if next_state.state_exit_function is not None:
            next_state.state_exit_function(self.context, self, timestep)

    def eol_process(self, env):
        """
        This process controls the state transitions for the component at
        each end-of-life (EOL) event.

        Parameters
        ----------
        env: simpy.Environment
            The environment in which this process is running.
        """
        while True:
            yield env.timeout(self.lifespan_timesteps)
            next_transition = self.context.choose_transition(self, env.now)
            self.transition(next_transition, env.now)


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
        max_timesteps: int = 200,
        years_per_timestep: float = 0.25,
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

        self.landfill_mass_inventory = Inventory(
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

        self.recycle_to_raw_mass_inventory = Inventory(
            name="mass that has been recycled to a raw material",
            possible_items=["nacelle", "blade", "tower", "foundation", ],
            timesteps=self.max_timesteps,
            quantity_unit="unit",
            can_be_negative=False,
        )

        self.recycle_to_clinker_mass_inventory = Inventory(
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
                             'recycling to raw material cost': []}


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


    def learning_by_doing(self, timestep):
        """
        This function so far only gets called if component.kind=='blade'
        :key
        """

        # needed for capacity expansion
        # blade_rec_count_ts = self.recycle_to_raw_component_inventory.component_materials['blade']

        # divide out the loss factor that's applied to the inventory
        # entire blades are processed through, but only 70% is kept in the supply chain
        # cost models should be based on mass processed, not mass output
        blade_rec_raw_mass_ts = self.recycle_to_raw_mass_inventory.component_materials['blade'] / 0.7
        blade_rec_clk_mass_ts = self.recycle_to_clinker_mass_inventory.component_materials['blade']

        # Calculate the pathway cost per tonne of stuff sent through the
        # pathway and that is how we will make our decision.

        # calculate tipping fee, USD/metric tonne
        landfill_tipping_fee = (3.0E-29) * np.exp(0.0344 * self.timesteps_to_years(timestep))

        # Recycling to Raw Materials: pathway net cost, USD per metric tonne
        recycling_process_cost_ts = self.cost_params['coarse_grinding_cost_init'] * (blade_rec_clk_mass_ts + blade_rec_raw_mass_ts + 1.0) ** -self.cost_params['recycling_learning_rate'] +\
        self.cost_params['fine_grinding_cost_init'] * (blade_rec_raw_mass_ts + 1.0) ** -self.cost_params['recycling_learning_rate']

        recycling_transpo_cost_ts = self.cost_params['recycling_transpo'] + self.cost_params['recycling_landfilling_transpo'] +\
        self.cost_params['recycling_to_raw_material_transpo']

        recycling_revenue_ts = self.cost_params['recycling_to_raw_material_revenue']

        # include the loss rate in this calculation - elsewhere it's built into
        # the input data
        recycling_landfill_cost_ts = 0.3 * landfill_tipping_fee

        cost_of_recycling_to_raw_material = recycling_process_cost_ts + recycling_transpo_cost_ts + recycling_landfill_cost_ts + recycling_revenue_ts

        # Recycling to Clinker: pathway net cost, USD per metric tonne
        recycling_clinker_process_cost_ts = self.cost_params['coarse_grinding_cost_init'] * (blade_rec_clk_mass_ts + blade_rec_raw_mass_ts + 1.0) ** -self.cost_params['recycling_learning_rate']

        recycling_clinker_transpo_cost_ts = self.cost_params['recycling_transpo'] + self.cost_params['recycling_to_clinker_transpo']

        recycling_clinker_revenue_ts = self.cost_params['recycling_to_clinker_revenue']

        cost_of_recycling_to_clinker = recycling_clinker_process_cost_ts + recycling_clinker_transpo_cost_ts + recycling_clinker_revenue_ts

        # Landfilling: pathway net cost, USD per metric tonne
        cost_of_landfilling = landfill_tipping_fee + self.cost_params['landfilling_transpo']

        # append the three pathway costs to the end of the cost-history dict,
        # but only if at least one of the values has changed
        if len(self.cost_history['year'])==0:

            self.cost_history['year'].append(self.timesteps_to_years(timestep))
            self.cost_history['landfilling cost'].append(cost_of_landfilling)
            self.cost_history['recycling to clinker cost'].append(cost_of_recycling_to_clinker)
            self.cost_history['recycling to raw material cost'].append(cost_of_recycling_to_raw_material)

        elif (self.cost_history['landfilling cost'][-1] != cost_of_landfilling) or\
                (self.cost_history['recycling to clinker cost'][-1] != cost_of_recycling_to_clinker) or\
                (self.cost_history['recycling to raw material cost'][-1] != cost_of_recycling_to_raw_material):

            self.cost_history['year'].append(self.timesteps_to_years(timestep))
            self.cost_history['landfilling cost'].append(cost_of_landfilling)
            self.cost_history['recycling to clinker cost'].append(cost_of_recycling_to_clinker)
            self.cost_history['recycling to raw material cost'].append(cost_of_recycling_to_raw_material)

        return cost_of_recycling_to_raw_material, cost_of_recycling_to_clinker, cost_of_landfilling


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
            if component.kind == 'blade' and self.timesteps_to_years(timestep) > 2019.0:

                (cost_of_recycling_to_raw_material,
                 cost_of_recycling_to_clinker,
                 cost_of_landfilling) = self.learning_by_doing(timestep)

                if min(cost_of_landfilling, cost_of_recycling_to_clinker,
                       cost_of_recycling_to_raw_material) == cost_of_landfilling:
                    _out = "landfilling"
                elif min(cost_of_landfilling, cost_of_recycling_to_clinker,
                             cost_of_recycling_to_raw_material) == cost_of_recycling_to_clinker:
                    _out = "recycling_to_clinker"
                else:
                    _out = "recycling_to_raw"

            else:
                # all other components get landfilled
                _out = "landfilling"

            return _out

        else:
            raise ValueError("Components must always be in the state use.")

    def run(self) -> Dict[str, pd.DataFrame]:
        """
        This method starts the discrete event simulation running.

        Returns
        -------
        Dict[str, pd.DataFrame]
            A dictionary of inventories mapped to their cumulative histories.
        """
        self.env.run(until=int(self.max_timesteps))
        inventories = {
            "landfill_component_inventory": self.landfill_component_inventory.cumulative_history,
            "landfill_mass_inventory": self.landfill_mass_inventory.cumulative_history,
            "virgin_component_inventory": self.virgin_component_inventory.cumulative_history,
            "virgin_material_inventory": self.virgin_material_inventory.cumulative_history,
            "recycle_to_raw_component_inventory": self.recycle_to_raw_component_inventory.cumulative_history,
            "recycle_to_raw_mass_inventory": self.recycle_to_raw_mass_inventory.cumulative_history,
            "recycle_to_clinker_component_inventory": self.recycle_to_clinker_component_inventory.cumulative_history,
            "recycle_to_clinker_mass_inventory": self.recycle_to_clinker_mass_inventory.cumulative_history,
            "cost_history": self.cost_history
        }
        return inventories
