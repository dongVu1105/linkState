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

    Add your own class fields and initialization code (e.g. to create forwarding table
    data structures). See the `Router` base class for docstrings of the methods to
    override.
    """

    def __init__(self, addr, heartbeat_time):
        """
        # Khởi tạo router với địa chỉ và thời gian nhịp tim
        # Thiết lập các cấu trúc dữ liệu cần thiết để quản lý mạng
        """
        Router.__init__(self, addr)  # Initialize base class
        self.heartbeat_time = heartbeat_time
        self.last_time = 0
        self.topology = {self.addr: {}}
        self.forwarding_table = {}
        self.seq_numbers = {self.addr: 0}
        self.port_to_neighbor = {}
        self.neighbor_to_port = {}

    def handle_packet(self, port, packet):
        """
        # Xử lý gói tin nhận được
        # Phân biệt giữa gói tin dữ liệu (traceroute) và gói tin định tuyến
        """
        if packet.is_traceroute:
            # Gói tin dữ liệu - chuyển tiếp nếu biết cổng ra
            if packet.dst_addr in self.forwarding_table:
                out_port = self.forwarding_table[packet.dst_addr]
                self.send(out_port, packet)
        else:
            # Gói tin định tuyến - xử lý thông tin trạng thái đường link
            try:
                router_addr, seq_number, link_state = json.loads(packet.content)
                # Chỉ xử lý nếu thông tin mới hơn thông tin hiện có
                if router_addr not in self.seq_numbers or seq_number > self.seq_numbers[router_addr]:
                    self.seq_numbers[router_addr] = seq_number
                    self.topology[router_addr] = link_state

                    # Tính toán lại bảng chuyển tiếp khi có thông tin mới
                    self.compute_forwarding_table()

                    # Chuyển tiếp gói tin đến các nút lân cận khác
                    for neighbor_port in self.links:
                        if neighbor_port != port:
                            self.send(neighbor_port, packet)
            except (json.JSONDecodeError, ValueError):
                pass

    def handle_new_link(self, port, endpoint, cost):
        """
        # Xử lý khi có một liên kết mới được thiết lập
        # Cập nhật thông tin topology và tính toán lại đường đi
        """
        self.port_to_neighbor[port] = endpoint
        self.neighbor_to_port[endpoint] = port
        self.topology[self.addr][endpoint] = cost
        self.compute_forwarding_table()
        self.broadcast_link_state()

    def handle_remove_link(self, port):
        """
        # Xử lý khi một liên kết bị ngắt kết nối
        # Cập nhật lại thông tin topology và tính toán lại đường đi
        """
        if port in self.port_to_neighbor:
            endpoint = self.port_to_neighbor[port]

            del self.port_to_neighbor[port]
            del self.neighbor_to_port[endpoint]

            if endpoint in self.topology[self.addr]:
                del self.topology[self.addr][endpoint]
            self.compute_forwarding_table()
            self.broadcast_link_state()

    def handle_time(self, time_ms):
        """
        # Xử lý theo thời gian
        # Thực hiện quảng bá định kỳ thông tin trạng thái đường link
        """
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self.broadcast_link_state()

    def broadcast_link_state(self):
        """
        # Quảng bá thông tin trạng thái đường link đến tất cả các láng giềng
        # Đảm bảo thông tin được lan truyền trong mạng
        """
        # Kiểm tra và khởi tạo số thứ tự cho router hiện tại
        if self.addr not in self.seq_numbers:
            self.seq_numbers[self.addr] = 0
            
        # Tăng số thứ tự để đánh dấu cập nhật mới
        self.seq_numbers[self.addr] += 1
        
        # Đóng gói thông tin trạng thái đường link
        link_state_info = [self.addr, self.seq_numbers[self.addr], self.topology[self.addr]]
        content = json.dumps(link_state_info)

        # Gửi gói tin đến tất cả các cổng kết nối
        for port in self.links:
            packet = Packet(Packet.ROUTING, self.addr, self.port_to_neighbor.get(port, "Unknown"), content)
            self.send(port, packet)

    def compute_forwarding_table(self):
        """
        # Tính toán bảng chuyển tiếp sử dụng thuật toán Dijkstra
        # Xác định đường đi ngắn nhất từ router hiện tại đến tất cả các điểm đến
        """
        # Khởi tạo các cấu trúc dữ liệu cho thuật toán
        dist = {self.addr: 0}         # Khoảng cách từ nguồn đến các nút
        prev = {}                     # Lưu nút trước đó trên đường đi ngắn nhất
        first_hop = {}                # Lưu nút đầu tiên trên đường đi
        pq = [(0, self.addr)]         # Hàng đợi ưu tiên (khoảng cách, nút)

        # Thực hiện thuật toán Dijkstra
        while pq:
            # Lấy nút có khoảng cách nhỏ nhất
            current_dist, current = heapq.heappop(pq)
            
            # Bỏ qua nếu đã tìm thấy đường đi tốt hơn
            if current in dist and current_dist > dist[current]:
                continue
                
            # Duyệt qua các nút kề
            if current in self.topology:
                for neighbor, cost in self.topology[current].items():
                    # Tính khoảng cách mới
                    new_dist = current_dist + cost
                    
                    # Cập nhật nếu tìm được đường đi ngắn hơn
                    if neighbor not in dist or new_dist < dist[neighbor]:
                        dist[neighbor] = new_dist
                        prev[neighbor] = current
                        
                        # Cập nhật thông tin về nút đầu tiên trên đường đi
                        if current == self.addr:
                            first_hop[neighbor] = neighbor
                        elif current in first_hop:
                            first_hop[neighbor] = first_hop[current]
                            
                        # Thêm vào hàng đợi để tiếp tục xử lý
                        heapq.heappush(pq, (new_dist, neighbor))

        # Xây dựng bảng chuyển tiếp từ kết quả thuật toán
        self.forwarding_table = {}
        for dst in first_hop:
            if first_hop[dst] in self.neighbor_to_port:
                self.forwarding_table[dst] = self.neighbor_to_port[first_hop[dst]]

    def __repr__(self):
        """
        # Biểu diễn router dưới dạng chuỗi để hiển thị trong trình mô phỏng mạng
        # Hiển thị thông tin liên kết, bảng chuyển tiếp và topology
        """
        output = f"LSrouter(addr={self.addr})\n"
        output += f"Links: {self.topology[self.addr]}\n"
        output += f"Forwarding Table: {self.forwarding_table}\n"
        output += f"Topology: {self.topology}\n"
        return output