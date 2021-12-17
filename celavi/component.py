from typing import Deque, Tuple, Dict
from collections import deque


class Component:
    def __init__(
        self,
        context,
        kind: str,
        year: int,
        lifespan_timesteps: float,
        manuf_facility_id: int,
        in_use_facility_id: int,
        mass_tonnes: Dict[str, float] = 0,
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

        year: int
            The year in which this component enters the use state for the first
            time.

        lifespan_timesteps: float
            The lifespan, in timesteps, of the component during its first
            In use phase. The argument can be
            provided as a floating point value, but it is converted into an
            integer before it is assigned to the instance attribute. This allows
            more intuitive integration with random number generators defined
            outside this class which may return floating point values.

        mass_tonnes: Dict[str, float]
            The masses of the materials of the component, in tonnes. Keys are
            material names. Values are material masses.

        manuf_facility_id: int
            The initial facility id (where the component begins life) used in
            initial pathway selection from CostGraph.

        in_use_facility_id: int
            The facility ID where the component spends its useful lifetime
            before beginning the end-of-life process.
        """

        self.context = context
        self.kind = kind
        self.year = year
        self.mass_tonnes = mass_tonnes
        self.manuf_facility_id = manuf_facility_id
        self.in_use_facility_id = in_use_facility_id
        self.current_location = 'manufacturing_' + str(self.manuf_facility_id)
        self.initial_lifespan_timesteps = int(lifespan_timesteps)  # timesteps
        self.pathway: Deque[Tuple[str, int]] = deque()
        self.split_dict = self.context.path_dict['path_split']

    def create_pathway_queue(self, from_facility_id: int):
        """
        Query the CostGraph and construct a queue of the lifecycle for
        this component. This method is called during the manufacturing step
        and during the eol_process when exiting an "in use" location.

        This method does not return anything, rather it modifies the
        instance attribute self.pathway with a new deque.

        Parameters
        ----------
        from_facility_id: int
            The starting location of the the component.
        """
        in_use_facility_id = f"in use_{int(from_facility_id)}"
        path_choices = self.context.cost_graph.choose_paths(source=in_use_facility_id)
        path_choices_dict = {path_choice['source']: path_choice for path_choice in path_choices}

        path_choice = path_choices_dict[in_use_facility_id]
        self.pathway = deque()

        for facility, lifespan, distance in path_choice['path']:
            # Override the initial timespan when component goes into use.

            if facility.startswith("in use"):
                self.pathway.append((facility, self.initial_lifespan_timesteps, distance))
            elif any([facility.startswith(i)
                      for i in self.context.path_dict['permanent_lifespan_facility']]):
                self.pathway.append((facility, self.context.max_timesteps * 2, distance))
            # Otherwise, use the timespan the model gives us.
            else:
                self.pathway.append((facility, lifespan, distance))

    def bol_process(self, env):
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
        begin_timestep = (self.year - self.context.min_year) * self.context.timesteps_per_year
        lifespan = 1

        # component waits to be manufactured
        yield env.timeout(begin_timestep)

        # Increment manufacturing inventories
        count_inventory = self.context.count_facility_inventories[self.current_location]
        mass_inventory = self.context.mass_facility_inventories[self.current_location]
        count_inventory.increment_quantity(self.kind, 1, env.now)
        for material, mass in self.mass_tonnes.items():
            mass_inventory.increment_quantity(material, mass, env.now)

        # Component waits to transition to in use
        yield env.timeout(lifespan)

        # Decrement manufacturing inventories
        # No transportation here: transportation is tracked at destination
        # facilities
        count_inventory.increment_quantity(self.kind, -1, env.now)
        for material, mass in self.mass_tonnes.items():
            mass_inventory.increment_quantity(material, -mass, env.now)

        # Component is now in use; update the location
        self.current_location = f"in use_{int(self.in_use_facility_id)}"

        # Increment in use inventories
        count_inventory = self.context.count_facility_inventories[self.current_location]
        mass_inventory = self.context.mass_facility_inventories[self.current_location]
        count_inventory.increment_quantity(self.kind, 1, env.now)
        for material, mass in self.mass_tonnes.items():
            mass_inventory.increment_quantity(material, mass, env.now)

        # Increment transportation to in use facilities
        count_transport = self.context.transportation_trackers[self.current_location]
        for _, mass in self.mass_tonnes.items():
            count_transport.increment_inbound_tonne_km(
                mass * self.context.cost_graph.supply_chain.edges[
                    f"manufacturing_{int(self.manuf_facility_id)}",
                    f"in use_{int(self.in_use_facility_id)}"
                ][
                    'dist'
                ],
                env.now
            )

        # Component stays in use for its lifetime
        yield env.timeout(self.initial_lifespan_timesteps)

        # Component's next steps are determined and stored in self.pathway
        self.create_pathway_queue(self.in_use_facility_id)

        # Component is decremented from in use inventories
        count_inventory.increment_quantity(self.kind, -1, env.now)
        for material, mass in self.mass_tonnes.items():
            mass_inventory.increment_quantity(material, -mass, env.now)

        # Take the current facility off the to-do list
        self.pathway.popleft()

        # Begin the end of life process
        env.process(self.eol_process(env))


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

            if len(self.pathway) > 0:
                location, lifespan, distance = self.pathway.popleft()
                factype = location.split('_')[0]
                if factype in self.split_dict.keys():
                    # increment the facility inventory and transpo tracker
                    fac_count_inventory = self.context.count_facility_inventories[location]
                    fac_transport = self.context.transportation_trackers[location]
                    fac_mass_inventory = self.context.mass_facility_inventories[location]
                    fac_count_inventory.increment_quantity(
                        self.kind,
                        1,
                        env.now
                    )

                    for _, mass in self.mass_tonnes.items():
                        fac_transport.increment_inbound_tonne_km(mass * distance, env.now)

                    for material, mass in self.mass_tonnes.items():
                        fac_mass_inventory.increment_quantity(material, mass, env.now)

                    # locate the nearest landfill and increment for material loss
                    _split_facility_1 = self.context.cost_graph.find_downstream(
                        facility_id = int(location.split('_')[1]),
                        connect_to = self.split_dict[factype]['facility_1']
                    )
                    _split_facility_2 = self.context.cost_graph.find_downstream(
                        node_name = location,
                        connect_to = self.split_dict[factype]['facility_2'])

                    fac1_count_inventory = self.context.count_facility_inventories[_split_facility_1]
                    fac1_transport = self.context.transportation_trackers[_split_facility_1]
                    fac1_mass_inventory = self.context.mass_facility_inventories[_split_facility_1]
                    fac1_count_inventory.increment_quantity(
                        self.kind,
                        self.split_dict[factype]['fraction'],
                        env.now
                    )

                    for material, mass in self.mass_tonnes.items():
                        fac1_transport.increment_inbound_tonne_km(
                            self.split_dict[factype]['fraction'] * mass * distance,
                            env.now
                        )
                        fac1_mass_inventory.increment_quantity(
                            material,
                            self.split_dict[factype]['fraction'] * mass,
                            env.now
                        )

                    fac2_count_inventory = self.context.count_facility_inventories[_split_facility_2]
                    fac2_mass_inventory = self.context.mass_facility_inventories[_split_facility_2]
                    fac2_transport = self.context.transportation_trackers[_split_facility_2]
                    fac2_count_inventory.increment_quantity(
                        self.kind,
                        1 - self.split_dict[factype]['fraction'],
                        env.now
                    )

                    for material, mass in self.mass_tonnes.items():
                        fac2_mass_inventory.increment_quantity(
                            material,
                            (1 - self.split_dict[factype]['fraction']) * mass,
                            env.now
                        )

                        fac2_transport.increment_inbound_tonne_km(
                            (1 - self.split_dict[factype]['fraction']) * mass * distance,
                            env.now
                        )

                    yield env.timeout(lifespan)

                    fac_count_inventory.increment_quantity(self.kind, -1, env.now)
                    for material, mass in self.mass_tonnes.items():
                        fac_mass_inventory.increment_quantity(material, -mass, env.now)

                elif factype in self.split_dict['pass']:
                    # the inventory and transportation was incremented when the
                    # blade hit the splitting step
                    pass

                else:
                    count_inventory = self.context.count_facility_inventories[location]
                    mass_inventory = self.context.mass_facility_inventories[location]
                    transport = self.context.transportation_trackers[location]
                    count_inventory.increment_quantity(self.kind, 1, env.now)

                    for material, mass in self.mass_tonnes.items():
                        mass_inventory.increment_quantity(material, mass, env.now)

                    # Again, assuming the transportation impacts are the same per unit
                    # mass for all materials.
                    for _, mass in self.mass_tonnes.items():
                        transport.increment_inbound_tonne_km(mass * distance, env.now)

                    self.current_location = location

                    yield env.timeout(lifespan)

                    count_inventory.increment_quantity(self.kind, -1, env.now)

                    for material, mass in self.mass_tonnes.items():
                        mass_inventory.increment_quantity(material, -mass, env.now)

            else:
                break
