#!/usr/bin/env python3

import time
import threading
import rclpy
from rclpy.node import Node
from mrs_msgs.srv import Vec4 
from std_srvs.srv import Trigger # Importado para o comando de Land (pouso)

class MrsFcuSquare(Node):

    def __init__(self):
        super().__init__('mrs_direct_square_node')
        
        # Clientes de serviço (utilizando nomes relativos ao namespace /uav1 do nó)
        self.goto_fcu_client = self.create_client(Vec4, 'control_manager/goto_fcu')
        self.land_client = self.create_client(Trigger, 'uav_manager/land') # Cliente do Land
        
        self.mission_thread = threading.Thread(target=self.run_mission)
        self.mission_thread.start()

    def run_mission(self):
        self.get_logger().info('Aguardando serviços ficarem ativos (goto_fcu e land)...')
        # Garante que ambos os serviços necessários estejam prontos no ecossistema
        while not self.goto_fcu_client.wait_for_service(timeout_sec=2.0) or not self.land_client.wait_for_service(timeout_sec=2.0):
            self.get_logger().info('Ainda aguardando serviços...')
            if not rclpy.ok():
                return
                
        self.get_logger().info('Serviços conectados! Iniciando sequência de voo...')
        time.sleep(2.0)

        # 1. Subida inicial (Z = 2.5 metros relativos ao chão)
        self.move_fcu(x=0.0, y=0.0, z=2.5, yaw=0.0, desc="Subida Inicial")
        time.sleep(10.0) # Tempo para o drone subir e estabilizar no ar

        # 2. Quadrado 2x2
        # Lado 1: Avança 2 metros para a frente
        self.move_fcu(x=2.0, y=0.0, z=0.0, yaw=0.0, desc="Lado 1: Frente 2m")
        time.sleep(7.0)

        # Lado 2: Move 2 metros para a esquerda
        self.move_fcu(x=0.0, y=2.0, z=0.0, yaw=0.0, desc="Lado 2: Esquerda 2m")
        time.sleep(7.0)

        # Lado 3: Recua 2 metros
        self.move_fcu(x=-2.0, y=0.0, z=0.0, yaw=0.0, desc="Lado 3: Trás 2m")
        time.sleep(7.0)

        # Lado 4: Move 2 metros para a direita (Fecha o quadrado)
        self.move_fcu(x=0.0, y=-2.0, z=0.0, yaw=0.0, desc="Lado 4: Direita 2m")
        time.sleep(7.0)

        # 3. Procedimento de Pouso Automático
        self.get_logger().info('Quadrado concluído! Iniciando procedimento de pouso (Land)...')
        req_land = Trigger.Request()
        
        future_land = self.land_client.call_async(req_land)
        
        # Aguarda a confirmação de recebimento do comando de pouso
        while rclpy.ok() and not future_land.done():
            time.sleep(0.1)
            
        self.get_logger().info('Comando de Land aceito pelo uav_manager. O drone está pousando!')

    def move_fcu(self, x, y, z, yaw, desc=""):
        self.get_logger().info(f'Enviando [{desc}] -> X:{x}, Y:{y}, Z:{z}')
        req = Vec4.Request()
        req.goal = [float(x), float(y), float(z), float(yaw)]
        
        future = self.goto_fcu_client.call_async(req)
        while rclpy.ok() and not future.done():
            time.sleep(0.05)


def main(args=None):
    rclpy.init(args=args)
    drone = MrsFcuSquare()
    try:
        rclpy.spin(drone)
    except KeyboardInterrupt:
        pass
    drone.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()