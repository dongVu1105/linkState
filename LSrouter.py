####################################################
# LSrouter.py
# Name:
# HUID:
#####################################################

from router import Router
import json
import heapq  # For Dijkstra's algorithm priority queue

class LSrouter(Router):
    """Link state routing protocol implementation.

    Add your own class fields and initialization code (e.g. to create forwarding table
    data structures). See the `Router` base class for docstrings of the methods to
    override.
    """

    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)  # Initialize base class - DO NOT REMOVE
        self.heartbeat_time = heartbeat_time
        self.last_time = 0
        
        # Store information about neighbors: {neighbor_addr: (port, cost)}
        self.neighbors = {}
        
        # Link state database: {router_addr: {neighbor_addr: cost}}
        self.link_states = {addr: {}}
        
        # Sequence numbers for received link states: {router_addr: seq_num}
        self.sequence_numbers = {}
        
        # My own sequence number
        self.sequence_number = 0
        
        # Forwarding table: {destination: outgoing_port}
        self.forwarding_table = {}

    def handle_packet(self, port, packet):
        """Process incoming packet."""
        if packet.is_traceroute:
            # Handle traceroute packet - forward to destination if known
            if packet.dst_addr in self.forwarding_table:
                out_port = self.forwarding_table[packet.dst_addr]
                self.send(out_port, packet)
        else:
            # Handle routing packet
            try:
                # Parse the link state packet
                lsp_data = json.loads(packet.content)
                sender = lsp_data["sender"]
                seq_num = lsp_data["seq_num"]
                links = lsp_data["links"]
                
                # Check if this is a newer link state update
                if sender not in self.sequence_numbers or seq_num > self.sequence_numbers[sender]:
                    # Store the sequence number
                    self.sequence_numbers[sender] = seq_num
                    
                    # Update the link state database
                    self.link_states[sender] = links
                    
                    # Recalculate the forwarding table
                    self._calculate_forwarding_table()
                    
                    # Broadcast the packet to all neighbors except the one we received from
                    for neighbor_addr, (neighbor_port, _) in self.neighbors.items():
                        if neighbor_port != port:
                            self.send(neighbor_port, packet)
            except (json.JSONDecodeError, KeyError) as e:
                # Log error or handle invalid packet
                pass

    def handle_new_link(self, port, endpoint, cost):
        """Handle new link."""
        # Update neighbor information
        self.neighbors[endpoint] = (port, cost)
        
        # Update my link state with the new neighbor
        self.link_states[self.addr][endpoint] = cost
        
        # Increment sequence number for a new link state packet
        self.sequence_number += 1
        
        # Broadcast link state to all neighbors
        self._broadcast_link_state()
        
        # Recalculate the forwarding table
        self._calculate_forwarding_table()

    def handle_remove_link(self, port):
        """Handle removed link."""
        # Find the endpoint that corresponds to this port
        endpoint_to_remove = None
        for endpoint, (p, _) in self.neighbors.items():
            if p == port:
                endpoint_to_remove = endpoint
                break
        
        # Remove the endpoint from neighbors if found
        if endpoint_to_remove:
            self.neighbors.pop(endpoint_to_remove)
            
            # Remove from my link state
            if endpoint_to_remove in self.link_states[self.addr]:
                self.link_states[self.addr].pop(endpoint_to_remove)
            
            # Increment sequence number
            self.sequence_number += 1
            
            # Broadcast updated link state
            self._broadcast_link_state()
            
            # Recalculate the forwarding table
            self._calculate_forwarding_table()

    def handle_time(self, time_ms):
        """Handle current time."""
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            
            # Broadcast link state periodically
            self._broadcast_link_state()

    def _broadcast_link_state(self):
        """Create and broadcast a link state packet to all neighbors."""
        lsp_data = {
            "sender": self.addr,
            "seq_num": self.sequence_number,
            "links": self.link_states[self.addr]
        }
        
        content = json.dumps(lsp_data)
        
        # Send to all neighbors
        for neighbor_addr, (port, _) in self.neighbors.items():
            from packet import Packet
            packet = Packet(Packet.ROUTING, self.addr, neighbor_addr, content)
            self.send(port, packet)

    def _calculate_forwarding_table(self):
        """Calculate shortest paths using Dijkstra's algorithm."""
        # Initialize distance and previous node dictionaries
        distances = {self.addr: 0}
        previous = {}
        unvisited = [(0, self.addr)]  # Priority queue (distance, node)
        
        # Process nodes in the priority queue
        while unvisited:
            current_distance, current_node = heapq.heappop(unvisited)
            
            # Check if we've found a shorter path already
            if current_distance > distances.get(current_node, float('inf')):
                continue
            
            # Get neighbors of the current node
            if current_node in self.link_states:
                for neighbor, cost in self.link_states[current_node].items():
                    distance = current_distance + cost
                    
                    # If we found a shorter path to neighbor
                    if distance < distances.get(neighbor, float('inf')):
                        distances[neighbor] = distance
                        previous[neighbor] = current_node
                        heapq.heappush(unvisited, (distance, neighbor))
        
        # Build forwarding table from shortest paths
        self.forwarding_table = {}
        
        for destination in distances:
            if destination != self.addr:
                # Trace back to find the first hop
                current = destination
                while previous.get(current) != self.addr:
                    if previous.get(current) is None:
                        break  # No path exists
                    current = previous[current]
                
                # If we found a valid path, add to forwarding table
                if previous.get(current) == self.addr:
                    port, _ = self.neighbors.get(current, (None, None))
                    if port is not None:
                        self.forwarding_table[destination] = port

    def __repr__(self):
        """Representation for debugging in the network visualizer."""
        neighbors_str = ", ".join([f"{addr}({port}, {cost})" for addr, (port, cost) in self.neighbors.items()])
        forwarding_str = ", ".join([f"{dst}->{port}" for dst, port in self.forwarding_table.items()])
        return f"LSrouter(addr={self.addr}, seq={self.sequence_number}, neighbors=[{neighbors_str}], forwarding=[{forwarding_str}])"