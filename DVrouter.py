import json
from router import Router
from packet import Packet


class DVrouter(Router):
    """Distance vector routing protocol implementation.

    Add your own class fields and initialization code (e.g. to create forwarding table
    data structures). See the `Router` base class for docstrings of the methods to
    override.
    """

    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)
        # VT khoảng cách: ánh xạ đích đến (chi phí, next_hop)
        self.dv_table = {addr: (0, None)}  # Đến chính mình thì chi phí là 0
        # Hàng xóm: ánh xạ từ cổng đến (neighbor_addr, cost)
        self.neighbor_links = {}
        self.last_broadcast = 0
        self.heartbeat_time = heartbeat_time
        self.INFINITY = 16  # Giá trị vô cực dùng trong rip

    def handle_new_link(self, port, endpoint, cost):
        # Thêm liên kết mới tới hàng xóm
        self.neighbor_links[port] = (endpoint, cost)
        
        # Nếu đây là đường đi tốt hơn hoặc chưa từng biết tới endpoint này thì cập nhật bảng DV
        if endpoint not in self.dv_table or cost < self.dv_table[endpoint][0]:
            self.dv_table[endpoint] = (cost, endpoint)
            self.broadcast_dv()

    def handle_remove_link(self, port):
        # Khi một liên kết bị ngắt
        if port in self.neighbor_links:
            neighbor = self.neighbor_links[port][0]
            del self.neighbor_links[port]
            # Xóa các đường đi mà next_hop là hàng xóm vừa bị ngắt
            changed = False
            for dst in list(self.dv_table.keys()):
                if dst != self.addr and self.dv_table[dst][1] == neighbor:
                    del self.dv_table[dst]
                    changed = True
            
            if changed:
                self.broadcast_dv()

    def handle_packet(self, port, packet):
        if packet.is_traceroute:
            # Nếu là gói dữ liệu traceroute: chuyển tiếp dựa trên bảng DV
            dst = packet.dst_addr
            if dst in self.dv_table:
                cost, next_hop = self.dv_table[dst]
                if next_hop is not None:  # Tìm cổng tương ứng với next_hop và gửi gói tin
                    for p, (neighbor, _) in self.neighbor_links.items():
                        if neighbor == next_hop:
                            self.send(p, packet)
                            break
        elif packet.is_routing:
             # Nếu là gói tin định tuyến: xử lý cập nhật từ hàng xóm
            try:
                neighbor_dv = json.loads(packet.content)
                neighbor_addr = packet.src_addr
                # Cập nhật distance vector
                changed = False
                for dst, cost in neighbor_dv.items():
                    # Không cập nhật đường đi tới chính mình
                    if dst != str(self.addr):  
                        neighbor_cost = self.neighbor_links[port][1]
                        new_cost = cost + neighbor_cost
                        # Nếu chưa có đường đi hoặc tìm được đường đi tốt hơn thì cập nhật
                        if dst not in self.dv_table or new_cost < self.dv_table[dst][0]:
                            self.dv_table[dst] = (new_cost, neighbor_addr)
                            changed = True
                        # Nếu next_hop là hàng xóm này và chi phí thay đổi thì cũng cập nhật
                        elif self.dv_table[dst][1] == neighbor_addr and new_cost != self.dv_table[dst][0]:
                            self.dv_table[dst] = (new_cost, neighbor_addr)
                            changed = True
                # Nếu có thay đổi thì gửi DV mới cho các hàng xóm
                if changed:
                    self.broadcast_dv()
            except json.JSONDecodeError:
                pass  

    def handle_time(self, time_ms):  # được gọi liên tục để xem liệu có đủ thời gian gửi DV mới hay ko
        if time_ms - self.last_broadcast >= self.heartbeat_time:
            self.broadcast_dv()
            self.last_broadcast = time_ms

    def broadcast_dv(self):
        # Gửi bảng vector khoảng cách hiện tại tới tất cả các hàng xóm
        dv_str = json.dumps({str(dst): cost for dst, (cost, _) in self.dv_table.items()})
        for port in self.neighbor_links:
            packet = Packet(Packet.ROUTING, self.addr, self.neighbor_links[port][0], dv_str)
            self.send(port, packet)
    
    def __repr__(self):
        return f"DVrouter(addr={self.addr}, dv={self.dv_table})"