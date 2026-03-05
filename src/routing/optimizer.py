"""Route optimizer for finding optimal POI visitation order."""

import asyncio
import logging
import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class RouteOptimizer:
    """Optimize route order using TSP and heuristics."""

    def __init__(
        self,
        max_iterations: int = 1000,
        convergence_threshold: int = 100,
    ) -> None:
        """Initialize route optimizer.

        Args:
            max_iterations: Maximum optimization iterations
            convergence_threshold: Iterations without improvement before stopping
        """
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold

    async def optimize_route(
        self,
        locations: list[dict[str, Any]],
        transport_mode: str = "walking",
        start: dict[str, float] | None = None,
        end: dict[str, float] | None = None,
        method: str = "simulated_annealing",
    ) -> list[int]:
        """Optimize route visiting all locations.

        Args:
            locations: List of locations with lat, lng
            transport_mode: Transport mode for speed calculation
            start: Optional start location
            end: Optional end location
            method: Optimization method

        Returns:
            Optimal order as indices
        """
        if len(locations) <= 2:
            return list(range(len(locations)))

        # Build distance matrix
        distance_matrix = self._build_distance_matrix(locations, start, end)

        # Select optimization method
        if method == "simulated_annealing":
            order = await self._simulated_annealing(distance_matrix)
        elif method == "genetic":
            order = await self._genetic_algorithm(distance_matrix)
        elif method == "nearest_neighbor":
            order = self._nearest_neighbor(distance_matrix)
        else:
            order = await self._simulated_annealing(distance_matrix)

        return order

    def _build_distance_matrix(
        self,
        locations: list[dict[str, Any]],
        start: dict[str, float] | None = None,
        end: dict[str, float] | None = None,
    ) -> np.ndarray:
        """Build distance matrix for locations.

        Args:
            locations: List of locations
            start: Optional start location
            end: Optional end location

        Returns:
            Distance matrix
        """
        n = len(locations)

        # Add start and end if provided
        if start:
            n += 1
        if end:
            n += 1

        matrix = np.zeros((n, n))

        # Build coordinates list
        coords = []
        if start:
            coords.append((start["lat"], start["lng"]))
        coords.extend([(loc["lat"], loc["lng"]) for loc in locations])
        if end:
            coords.append((end["lat"], end["lng"]))

        # Calculate distances
        for i in range(n):
            for j in range(n):
                if i != j:
                    matrix[i][j] = self._haversine_distance(
                        coords[i][0],
                        coords[i][1],
                        coords[j][0],
                        coords[j][1],
                    )

        return matrix

    def _haversine_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """Calculate Haversine distance between two points.

        Args:
            lat1: Latitude of first point
            lon1: Longitude of first point
            lat2: Latitude of second point
            lon2: Longitude of second point

        Returns:
            Distance in kilometers
        """
        import math

        R = 6371  # Earth radius in km

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = (
            math.sin(dlat / 2) ** 2 +
            math.cos(math.radians(lat1)) *
            math.cos(math.radians(lat2)) *
            math.sin(dlon / 2) ** 2
        )

        c = 2 * math.asin(math.sqrt(a))

        return R * c

    def _nearest_neighbor(self, distance_matrix: np.ndarray) -> list[int]:
        """Nearest neighbor heuristic for TSP.

        Args:
            distance_matrix: Distance matrix

        Returns:
            Order of visits
        """
        n = len(distance_matrix)
        visited = [False] * n
        order = []

        # Start from first node
        current = 0
        order.append(current)
        visited[current] = True

        # Visit nearest unvisited node
        for _ in range(n - 1):
            nearest = -1
            min_dist = float("inf")

            for i in range(n):
                if not visited[i] and distance_matrix[current][i] < min_dist:
                    min_dist = distance_matrix[current][i]
                    nearest = i

            if nearest >= 0:
                order.append(nearest)
                visited[nearest] = True
                current = nearest

        return order

    async def _simulated_annealing(
        self,
        distance_matrix: np.ndarray,
        initial_temp: float = 1000.0,
        cooling_rate: float = 0.995,
    ) -> list[int]:
        """Simulated annealing for TSP.

        Args:
            distance_matrix: Distance matrix
            initial_temp: Initial temperature
            cooling_rate: Cooling rate per iteration

        Returns:
            Optimized order
        """
        n = len(distance_matrix)

        # Initial solution using nearest neighbor
        current_order = self._nearest_neighbor(distance_matrix)
        current_distance = self._calculate_total_distance(current_order, distance_matrix)

        best_order = current_order.copy()
        best_distance = current_distance

        temp = initial_temp
        no_improvement = 0

        for iteration in range(self.max_iterations):
            # Generate neighbor by swapping two cities
            neighbor_order = current_order.copy()
            i, j = random.sample(range(n), 2)
            neighbor_order[i], neighbor_order[j] = neighbor_order[j], neighbor_order[i]

            neighbor_distance = self._calculate_total_distance(
                neighbor_order,
                distance_matrix
            )

            # Accept or reject
            delta = neighbor_distance - current_distance

            if delta < 0 or random.random() < math.exp(-delta / temp):
                current_order = neighbor_order
                current_distance = neighbor_distance

                if current_distance < best_distance:
                    best_order = current_order.copy()
                    best_distance = current_distance
                    no_improvement = 0
                else:
                    no_improvement += 1
            else:
                no_improvement += 1

            # Cool down
            temp *= cooling_rate

            # Check convergence
            if no_improvement >= self.convergence_threshold:
                logger.info(f"Converged at iteration {iteration}")
                break

        logger.info(f"Simulated annealing: best distance = {best_distance:.2f} km")

        return best_order

    async def _genetic_algorithm(
        self,
        distance_matrix: np.ndarray,
        population_size: int = 50,
        mutation_rate: float = 0.02,
        elite_size: int = 5,
    ) -> list[int]:
        """Genetic algorithm for TSP.

        Args:
            distance_matrix: Distance matrix
            population_size: Size of population
            mutation_rate: Mutation probability
            elite_size: Number of elite individuals

        Returns:
            Optimized order
        """
        n = len(distance_matrix)

        # Initialize population
        population = []
        for _ in range(population_size):
            order = list(range(n))
            random.shuffle(order)
            population.append(order)

        best_order = population[0].copy()
        best_distance = self._calculate_total_distance(best_order, distance_matrix)

        for generation in range(self.max_iterations // 10):
            # Evaluate fitness
            fitness = []
            for individual in population:
                distance = self._calculate_total_distance(individual, distance_matrix)
                fitness.append(1 / (distance + 1))  # Fitness is inverse of distance

            # Selection
            selected = self._selection(population, fitness, elite_size)

            # Crossover
            offspring = []
            for i in range(0, len(selected) - 1, 2):
                parent1 = selected[i]
                parent2 = selected[i + 1]
                child1, child2 = self._crossover(parent1, parent2)
                offspring.extend([child1, child2])

            # Mutation
            for individual in offspring:
                if random.random() < mutation_rate:
                    i, j = random.sample(range(n), 2)
                    individual[i], individual[j] = individual[j], individual[i]

            # New population
            population = selected[:elite_size] + offspring[:population_size - elite_size]

            # Track best
            for individual in population:
                distance = self._calculate_total_distance(individual, distance_matrix)
                if distance < best_distance:
                    best_order = individual.copy()
                    best_distance = distance

        logger.info(f"Genetic algorithm: best distance = {best_distance:.2f} km")

        return best_order

    def _selection(
        self,
        population: list[list[int]],
        fitness: list[float],
        elite_size: int,
    ) -> list[list[int]]:
        """Select individuals for next generation.

        Args:
            population: Current population
            fitness: Fitness values
            elite_size: Number of elites

        Returns:
            Selected individuals
        """
        # Sort by fitness
        sorted_pop = [x for _, x in sorted(zip(fitness, population), reverse=True)]

        # Keep elites
        selected = sorted_pop[:elite_size]

        # Tournament selection for rest
        while len(selected) < len(population):
            # Select 5 random individuals
            tournament = random.sample(population, min(5, len(population)))
            winner = max(tournament, key=lambda x: fitness[population.index(x)])
            selected.append(winner.copy())

        return selected

    def _crossover(
        self,
        parent1: list[int],
        parent2: list[int],
    ) -> tuple[list[int], list[int]]:
        """Order crossover (OX) for TSP.

        Args:
            parent1: First parent
            parent2: Second parent

        Returns:
            Two offspring
        """
        n = len(parent1)

        # Select random segment
        start, end = sorted(random.sample(range(n), 2))

        # Create offspring
        child1 = [-1] * n
        child2 = [-1] * n

        # Copy segment
        child1[start:end] = parent1[start:end]
        child2[start:end] = parent2[start:end]

        # Fill remaining from other parent
        def fill_child(child, other_parent):
            ptr = (end) % n
            for val in other_parent:
                if val not in child:
                    child[ptr] = val
                    ptr = (ptr + 1) % n

        fill_child(child1, parent2)
        fill_child(child2, parent1)

        return child1, child2

    def _calculate_total_distance(
        self,
        order: list[int],
        distance_matrix: np.ndarray,
    ) -> float:
        """Calculate total distance for an order.

        Args:
            order: Order of visits
            distance_matrix: Distance matrix

        Returns:
            Total distance
        """
        total = 0.0
        for i in range(len(order) - 1):
            total += distance_matrix[order[i]][order[i + 1]]
        return total


class TimeWindowOptimizer(RouteOptimizer):
    """Optimizer with time window constraints."""

    async def optimize_with_time_windows(
        self,
        locations: list[dict[str, Any]],
        time_windows: dict[str, tuple[datetime, datetime]],
        service_times: dict[str, int],
        transport_mode: str = "walking",
        start: dict[str, float] | None = None,
        start_time: datetime | None = None,
    ) -> tuple[list[int], dict[str, Any]]:
        """Optimize route with time window constraints.

        Args:
            locations: List of locations
            time_windows: Time windows for each location
            service_times: Service time for each location (minutes)
            transport_mode: Transport mode
            start: Optional start location
            start_time: Optional start time

        Returns:
            Tuple of (order, schedule_info)
        """
        if not start_time:
            start_time = datetime.now(timezone.utc)

        # Build distance matrix with travel times
        distance_matrix = self._build_distance_matrix(locations, start)

        # Convert to time matrix
        time_matrix = self._distance_to_time_matrix(distance_matrix, transport_mode)

        # Solve with time windows
        order = await self._solve_with_time_windows(
            time_matrix,
            time_windows,
            service_times,
            start_time,
        )

        # Build schedule
        schedule = self._build_schedule(
            order,
            time_matrix,
            time_windows,
            service_times,
            start_time,
        )

        return order, schedule

    def _distance_to_time_matrix(
        self,
        distance_matrix: np.ndarray,
        transport_mode: str,
    ) -> np.ndarray:
        """Convert distance matrix to time matrix.

        Args:
            distance_matrix: Distance matrix (km)
            transport_mode: Transport mode

        Returns:
            Time matrix (minutes)
        """
        speeds = {
            "walking": 5.0,
            "driving": 30.0,
            "transit": 20.0,
        }

        speed = speeds.get(transport_mode, 5.0)

        # Convert km to minutes
        return (distance_matrix / speed) * 60

    async def _solve_with_time_windows(
        self,
        time_matrix: np.ndarray,
        time_windows: dict[str, tuple[datetime, datetime]],
        service_times: dict[str, int],
        start_time: datetime,
    ) -> list[int]:
        """Solve TSP with time windows using insertion heuristic.

        Args:
            time_matrix: Time matrix
            time_windows: Time windows
            service_times: Service times
            start_time: Start time

        Returns:
            Order of visits
        """
        n = len(time_matrix)
        unvisited = set(range(n))
        order = []

        current_time = start_time
        current_idx = 0

        while unvisited:
            best_next = -1
            best_score = float("-inf")

            for next_idx in unvisited:
                # Calculate arrival time
                travel_time = time_matrix[current_idx][next_idx]
                arrival_time = current_time + timedelta(minutes=travel_time)

                # Check time window
                location_id = str(next_idx)
                if location_id in time_windows:
                    window_start, window_end = time_windows[location_id]

                    if arrival_time < window_start:
                        arrival_time = window_start  # Wait until window opens
                    elif arrival_time > window_end:
                        continue  # Can't visit, window closed

                # Calculate score (prefer earlier windows)
                score = -travel_time

                if location_id in time_windows:
                    window_start, _ = time_windows[location_id]
                    time_to_window = (window_start - arrival_time).total_seconds() / 60
                    score -= abs(time_to_window) * 0.1

                if score > best_score:
                    best_score = score
                    best_next = next_idx

            if best_next < 0:
                break

            order.append(best_next)
            unvisited.remove(best_next)

            # Update current time
            travel_time = time_matrix[current_idx][best_next]
            current_time = current_time + timedelta(minutes=travel_time)

            location_id = str(best_next)
            if location_id in time_windows:
                window_start, _ = time_windows[location_id]
                if current_time < window_start:
                    current_time = window_start

            service_time = service_times.get(location_id, 30)
            current_time = current_time + timedelta(minutes=service_time)

            current_idx = best_next

        return order

    def _build_schedule(
        self,
        order: list[int],
        time_matrix: np.ndarray,
        time_windows: dict[str, tuple[datetime, datetime]],
        service_times: dict[str, int],
        start_time: datetime,
    ) -> dict[str, Any]:
        """Build detailed schedule.

        Args:
            order: Visit order
            time_matrix: Time matrix
            time_windows: Time windows
            service_times: Service times
            start_time: Start time

        Returns:
            Schedule information
        """
        schedule = {
            "stops": [],
            "total_time_minutes": 0,
            "total_travel_time_minutes": 0,
            "total_service_time_minutes": 0,
        }

        current_time = start_time
        current_idx = 0

        for idx in order:
            location_id = str(idx)

            # Travel time
            travel_time = time_matrix[current_idx][idx]
            arrival_time = current_time + timedelta(minutes=travel_time)

            # Check time window
            window_start, window_end = time_windows.get(location_id, (None, None))

            if window_start and arrival_time < window_start:
                arrival_time = window_start  # Wait

            # Service time
            service_time = service_times.get(location_id, 30)
            departure_time = arrival_time + timedelta(minutes=service_time)

            schedule["stops"].append({
                "location_id": location_id,
                "arrival_time": arrival_time.isoformat(),
                "departure_time": departure_time.isoformat(),
                "travel_time_minutes": travel_time,
                "service_time_minutes": service_time,
                "time_window": (
                    f"{window_start.isoformat()} - {window_end.isoformat()}"
                    if window_start and window_end
                    else None
                ),
            })

            schedule["total_travel_time_minutes"] += travel_time
            schedule["total_service_time_minutes"] += service_time

            current_time = departure_time
            current_idx = idx

        schedule["total_time_minutes"] = (
            schedule["total_travel_time_minutes"] +
            schedule["total_service_time_minutes"]
        )

        return schedule


# Global instances
route_optimizer = RouteOptimizer()
time_window_optimizer = TimeWindowOptimizer()


def get_route_optimizer() -> RouteOptimizer:
    """Get route optimizer instance.

    Returns:
        Route optimizer instance
    """
    return route_optimizer


def get_time_window_optimizer() -> TimeWindowOptimizer:
    """Get time window optimizer instance.

    Returns:
        Time window optimizer instance
    """
    return time_window_optimizer
