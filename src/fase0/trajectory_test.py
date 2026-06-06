#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
import time

from mrs_msgs.msg import Reference, Path
from mrs_msgs.srv import PathSrv, String as MrsString
from std_srvs.srv import Trigger

#Aqui o slow, fast e medium funcionam!!!
#O sistema de coordenadas é Y positivo para esquerda; x positivo para frente, z positivo para cima (é o do Clover)

class MRSWaypointMissionClient(Node):
    def __init__(self):
        super().__init__('mrs_waypoint_mission_client')
        
        # Garante o sincronismo de tempo com o simulador (Gazebo)
        self.set_parameters([Parameter('use_sim_time', Parameter.Type.BOOL, True)])
        
        self.set_constraints_client = self.create_client(MrsString, '/uav1/constraint_manager/set_constraints')

        # Cliente do Gerador de Trajetória
        self.gen_client = self.create_client(PathSrv, '/uav1/trajectory_generation/path')
        
        # Clientes do Control Manager e UAV Manager
        self.goto_start_client = self.create_client(Trigger, '/uav1/control_manager/goto_trajectory_start')
        self.start_client = self.create_client(Trigger, '/uav1/control_manager/start_trajectory_tracking')
        self.land_client = self.create_client(Trigger, '/uav1/uav_manager/land')
        
        self.get_logger().info('Aguardando conexão com os serviços do MRS...')
        self.gen_client.wait_for_service()
        self.goto_start_client.wait_for_service()
        self.start_client.wait_for_service()
        self.land_client.wait_for_service()
        self.get_logger().info('Todos os serviços conectados com sucesso!')

    def change_speed(self, profile_name):
        self.get_logger().info(f'Alterando perfil de velocidade para: {profile_name}')
        req = MrsString.Request()
        req.value = str(profile_name)
        self.set_constraints_client.call_async(req)

    def enviar_e_executar_ponto(self, x, y, z, heading=0.0, tempo_voo_estimado=8.0):
        """Monta o Path para um único ponto, gera a trajetória e executa"""
        caminho = Path()

        #'body' é uav1/fcu_untilted
        #honestamente não sei quando é melhor usar fixed_origin e local_origin para o 'map'
        caminho.header.frame_id = 'uav1/fixed_origin'
        caminho.header.stamp = self.get_clock().now().to_msg()
        
        p = Reference()
        p.position.x = float(x)
        p.position.y = float(y)
        p.position.z = float(z)
        p.heading = float(heading)
        caminho.points = [p]
        
        # 1. Envia para o gerador
        req_gen = PathSrv.Request()
        req_gen.path = caminho
        future_gen = self.gen_client.call_async(req_gen)
        rclpy.spin_until_future_complete(self, future_gen)
        
        if not (future_gen.result() and future_gen.result().success):
            self.get_logger().error(f'O gerador rejeitou o ponto ({x}, {y}, {z})')
            return False
            
        # 2. Alinha o drone no início do trajeto
        req_goto = Trigger.Request()
        future_goto = self.goto_start_client.call_async(req_goto)
        rclpy.spin_until_future_complete(self, future_goto)
        
        if not (future_goto.result() and future_goto.result().success):
            self.get_logger().error('O Control Manager recusou alinhar no ponto.')
            return False
            
        # Tempo de deslocamento seguro para o drone chegar até a coordenada física
        #time.sleep(tempo_voo_estimado)
        
        # 3. Executa o rastreamento final da trajetória polinomial
        req_start = Trigger.Request()
        future_start = self.start_client.call_async(req_start)
        rclpy.spin_until_future_complete(self, future_start)
        
        if future_start.result() and future_start.result().success:
            self.get_logger().info(f'Drone chegou com sucesso na coordenada ({x}, {y}, {z})!')
            return True
        else:
            self.get_logger().error('Falha ao dar START no rastreamento.')
            return False

    def executar_missao(self):
        # Lista de coordenadas solicitadas: (x, y, z)
        coordenadas = [
            (2.0, 6.0, 2.5, 'slow'),
            (-2.5, 0.0, 2.5, 'slow'),
            (2.0, -5.0, 2.5, 'slow')
        ]
        
        for i, (x, y, z, r) in enumerate(coordenadas, 1):
            self.get_logger().info(f'--- Iniciando Ponto {i}: Indo para ({x}, {y}, {z}) ---')
            
            # Executa o movimento. (Aumente o tempo_voo_estimado se os pontos forem longe demais um do outro)
            self.change_speed(r)
            sucesso = self.enviar_e_executar_ponto(x, y, z, heading=0.0, tempo_voo_estimado=10.0)
            
            if sucesso:
                self.get_logger().info(f'Aguardando 10 segundos parado no ponto {i}...')
                time.sleep(10.0)
            else:
                self.get_logger().error(f'Interrompendo missão devido a falha no ponto {i}.')
                return

        # --- FIM DA MISSÃO: POUSAR ---
        self.get_logger().info('--- Todas as coordenadas concluídas. Iniciando o pouso automático... ---')
        req_land = Trigger.Request()
        future_land = self.land_client.call_async(req_land)
        rclpy.spin_until_future_complete(self, future_land)
        
        if future_land.result() and future_land.result().success:
            self.get_logger().info('Comando de pouso (Land) aceito. Missão finalizada!')
        else:
            self.get_logger().error('O UAV Manager rejeitou o comando de pouso.')

def main(args=None):
    rclpy.init(args=args)
    node = MRSWaypointMissionClient()
    node.executar_missao()
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()