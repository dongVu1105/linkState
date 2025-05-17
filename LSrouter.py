####################################################
# LSrouter.py
# Name: Link State Router Implementation
# HUID:
#####################################################

import heapq
import json

from packet import Packet
from router import Router


class LSrouter(Router):
    """Link state routing protocol implementation.

    This implementation maintains a global view of the network topology
    and uses Dijkstra's algorithm to compute shortest paths.
    """

    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)  # Initialize base class
        self.heartbeat_time = heartbeat_time
        self.last_time = 0
        self.topology = {self.addr: {}}
        self.forwarding_table = {}
        self.seq_numbers = {self.addr: 0}
        self.port_to_neighbor = {}
        self.neighbor_to_port = {}

    def handle_packet(self, port, packet):
        """Process incoming packet."""
        if packet.is_traceroute:
            # data packet
            if packet.dst_addr in self.forwarding_table:
                out_port = self.forwarding_table[packet.dst_addr]
                self.send(out_port, packet)
        else:
            #routing packet
            try:
                router_addr, seq_number, link_state = json.loads(packet.content)
                if router_addr not in self.seq_numbers or seq_number > self.seq_numbers[router_addr]:
                    self.seq_numbers[router_addr] = seq_number
                    self.topology[router_addr] = link_state

                    self.compute_forwarding_table()

                    for neighbor_port in self.links:
                        if neighbor_port != port:
                            self.send(neighbor_port, packet)
            except (json.JSONDecodeError, ValueError):
                pass

    def handle_new_link(self, port, endpoint, cost):
        """Handle new link."""
        self.port_to_neighbor[port] = endpoint
        self.neighbor_to_port[endpoint] = port
        self.topology[self.addr][endpoint] = cost
        self.compute_forwarding_table()
        self.broadcast_link_state()

    def handle_remove_link(self, port):
        """Handle removed link."""
        if port in self.port_to_neighbor:
            endpoint = self.port_to_neighbor[port]

            del self.port_to_neighbor[port]
            del self.neighbor_to_port[endpoint]

            if endpoint in self.topology[self.addr]:
                del self.topology[self.addr][endpoint]
            self.compute_forwarding_table()
            self.broadcast_link_state()

    def handle_time(self, time_ms):
        """Handle current time."""
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self.broadcast_link_state()

    def broadcast_link_state(self):
        """Broadcast our link state to all neighbors."""
        if self.addr not in self.seq_numbers:
            self.seq_numbers[self.addr] = 0
        self.seq_numbers[self.addr] += 1
        link_state_info = [self.addr, self.seq_numbers[self.addr], self.topology[self.addr]]
        content = json.dumps(link_state_info)

        for port in self.links:
            packet = Packet(Packet.ROUTING, self.addr, self.port_to_neighbor.get(port, "Unknown"), content)
            self.send(port, packet)

    def compute_forwarding_table(self):
        """Compute shortest paths using Dijkstra's algorithm."""
        dist = {self.addr: 0}
        prev = {}
        first_hop = {}
        pq = [(0, self.addr)]

        while pq:
            current_dist, current = heapq.heappop(pq)
            if current in dist and current_dist > dist[current]:
                continue
            if current in self.topology:
                for neighbor, cost in self.topology[current].items():
                    new_dist = current_dist + cost
                    if neighbor not in dist or new_dist < dist[neighbor]:
                        dist[neighbor] = new_dist
                        prev[neighbor] = current
                        if current == self.addr:
                            first_hop[neighbor] = neighbor
                        elif current in first_hop:
                            first_hop[neighbor] = first_hop[current]
                        heapq.heappush(pq, (new_dist, neighbor))

        self.forwarding_table = {}
        for dst in first_hop:
            if first_hop[dst] in self.neighbor_to_port:
                self.forwarding_table[dst] = self.neighbor_to_port[first_hop[dst]]

    def __repr__(self):
        """Representation for debugging in the network visualizer."""
        output = f"LSrouter(addr={self.addr})\n"
        output += f"Links: {self.topology[self.addr]}\n"
        output += f"Forwarding Table: {self.forwarding_table}\n"
        output += f"Topology: {self.topology}\n"
        return output