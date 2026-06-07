#!/usr/bin/python3
import math
import os
import time
import numpy as np
import colorful as cf

from states import TakeOff

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup

from mrs_msgs.msg import Reference, ReferenceStamped, Path, ControlManagerDiagnostics
from mrs_msgs.srv import TransformReferenceSrv, PathSrv, String as MrsString
from std_srvs.srv import Trigger, SetBool
from nav_msgs.msg import Odometry

class Tools(Node):
    def __init__(self, node_name='tools_node') -> None:
        super().__init__(node_name)

        self.fsm = TakeOff()
        self.start_phase = False

        self.cbkgr_navigate = ReentrantCallbackGroup()
        self.cbkgr_emergency = MutuallyExclusiveCallbackGroup()

        self.cbkgr_sc = MutuallyExclusiveCallbackGroup()

        self.telem = {'x':0.0, 'y':0.0, 'z':0.0, 'yaw':0.0}
        self.sub_control_manager_diag = None

    def setSubscribers(self):

        self.odom_sub = self.create_subscription(
            Odometry,
            '/uav1/estimation_manager/odom_main',
            self.odom_callback,
            10
        )

        self.sub_diag = self.create_subscription(
            ControlManagerDiagnostics,
            '/uav1/control_manager/diagnostics',
            self.callback_diagnostics,
            10 
        )

    def setPublishers(self):
        None
    
    def setClients(self):

        self.client_arming = self.create_client(
            SetBool, 
            '/uav1/hw_api/arming', 
            callback_group=self.cbkgr_navigate
        )

        self.client_offboard = self.create_client(
            Trigger, 
            '/uav1/hw_api/offboard', 
            callback_group=self.cbkgr_navigate
        )

        self.client_set_constraints = self.create_client(
            MrsString,
            '/uav1/constraint_manager/set_constraints',
            callback_group=self.cbkgr_navigate
        )

        self.client_gen_trjct = self.create_client(
            PathSrv,
            '/uav1/trajectory_generation/path',
            callback_group=self.cbkgr_navigate
        )
       
        self.client_goto_trjct_start = self.create_client(
            Trigger,
            '/uav1/control_manager/goto_trajectory_start',
            callback_group=self.cbkgr_navigate
        )

        self.client_start_trjct = self.create_client(
            Trigger,
            '/uav1/control_manager/start_trajectory_tracking',
            callback_group=self.cbkgr_navigate
        )

        self.client_stop_trjct = self.create_client(
            Trigger, 
            '/uav1/control_manager/stop_trajectory_tracking', 
            callback_group=self.cbkgr_emergency
        )    
        
        self.client_transform = self.create_client(
            TransformReferenceSrv,
            '/uav1/control_manager/transform_reference',
            callback_group=self.cbkgr_emergency
        )
        
        #self.client_stop_rfrc = self.create_client(
        #    Trigger, 
        #    '/uav1/control_manager/hover', 
        #    callback_group=self.cbkgr_emergency
        #)

        self.client_land = self.create_client(
            Trigger,
            '/uav1/uav_manager/land',
            callback_group=self.cbkgr_navigate
        )

        print(cf.yellow('Aguardando conexão com os serviços do MRS...'))
        self.client_arming.wait_for_service()
        self.client_offboard.wait_for_service()
        self.client_set_constraints.wait_for_service()
        self.client_gen_trjct.wait_for_service()
        self.client_goto_trjct_start.wait_for_service()
        self.client_start_trjct.wait_for_service()
        #self.client_stop_trjct.wait_for_service()
        self.client_transform.wait_for_service()
        #self.client_stop_rfrc.wait_for_service()
        self.client_land.wait_for_service()
        print(cf.yellow('Todos os serviços conectados com sucesso!'))

    def setServer(self):

        self.ss_start = self.create_service(
            Trigger, 
            "~/start_phase", 
            self.startPhase, 
            callback_group=self.cbkgr_sc
        )

    def startPhase(self, request, response):
        self.start_phase = True

        response.success = True
        response.message = "Fase iniciada"

        return response

    def callback_diagnostics(self, msg):
        self.sub_control_manager_diag = msg

    def odom_callback(self, msg):
        self.telem['x'] = msg.pose.pose.position.x
        self.telem['y'] = msg.pose.pose.position.y
        self.telem['z'] = msg.pose.pose.position.z

        q = msg.pose.pose.orientation

        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        self.telem['yaw'] = math.atan2(siny_cosp, cosy_cosp)

    def changePace(self, profile_name):
    
        req = MrsString.Request()
        req.value = str(profile_name)

        future = self.client_set_constraints.call_async(req)
        rclpy.spin_until_future_complete(self, future)

        res = future.result()
        if res is not None and res.success:
            print(cf.green(f"Velocidade de voo alterada com sucesso para {profile_name}"))
            return True
        else:
            print(cf.red("Erro ao alterar velocidade de voo"))
            return False

    def navigateArm(self):

        req = SetBool.Request()
        req.data = True

        future = self.client_arming.call_async(req)
        rclpy.spin_until_future_complete(self, future)

        res = future.result()
        if res is not None and res.success:
            print(cf.green("Motores armados com sucesso"))
            return True
        else:
            print(cf.red("Falha ao armar"))
            return False

    def navigateOffboard(self):

        req = Trigger.Request()

        future = self.client_offboard.call_async(req)
        rclpy.spin_until_future_complete(self, future)

        res = future.result()
        if res is not None and res.success:
            print(cf.green("Offboard aceito pelo SITL"))
            return True
        else:
            print(cf.red("Offboard rejeitado pelo SITL"))
            return False

    def navigateTrajectory(self, x=0, y=0, z=0, yaw=0, speed='slow', frame='uav1/fixed_origin'):

        #Speed possíveis: 'slow', 'medium' e 'fast'
        #Frames possíveis: 'uav1/fcu_untilted' (body), 'uav1/fixed_origin' ou 'uav1/local_origin' (map) -> Averiguar diferenças entre fixed e local

        print(cf.blue(f"Navigate iniciado para o ponto ({x}, {y}, {z}) no frame '{frame}'"))
        
        self.changePace(speed)
    
        tempo_atual = rclpy.time.Time().to_msg() 

        p_alvo = Reference()
        p_alvo.position.x = float(x)
        p_alvo.position.y = float(y)
        p_alvo.position.z = float(z)
        p_alvo.heading = float(yaw)

        p_stamped = ReferenceStamped()
        p_stamped.header.frame_id = str(frame)
        p_stamped.header.stamp = tempo_atual
        p_stamped.reference = p_alvo

        req_trans = TransformReferenceSrv.Request()
        req_trans.frame_id = "uav1/fixed_origin"
        req_trans.reference = p_stamped
        
        future_trans = self.client_transform.call_async(req_trans)
        rclpy.spin_until_future_complete(self, future_trans)
        
        res_trans = future_trans.result()
        if res_trans and res_trans.success:
            p_destino = res_trans.reference.reference
            
            x_global = p_destino.position.x
            y_global = p_destino.position.y
            z_global = p_destino.position.z
            yaw_global = p_destino.heading

        p_atual = Reference()
        p_atual.position.x = float(self.telem['x'])
        p_atual.position.y = float(self.telem['y'])
        p_atual.position.z = float(self.telem['z'])
        p_atual.heading = float(self.telem['yaw'])

        route = Path()
        route.header.frame_id = "uav1/fixed_origin"
        route.header.stamp = tempo_atual
        route.points = [p_atual, p_destino]

        req_gen = PathSrv.Request()
        req_gen.path = route
        future_gen = self.client_gen_trjct.call_async(req_gen)
        rclpy.spin_until_future_complete(self, future_gen)

        if not (future_gen.result() and future_gen.result().success):
            print(cf.red(f'O gerador do MRS rejeitou a trajetória para ({x_global}, {y_global}, {z_global})'))
            return False

        req_goto = Trigger.Request()
        future_goto = self.client_goto_trjct_start.call_async(req_goto)
        rclpy.spin_until_future_complete(self, future_goto)
        
        if not (future_goto.result() and future_goto.result().success):
            print(cf.red('O Control Manager recusou alinhar no início da trajetória.'))
            return False
        
        while rclpy.ok():
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.sub_control_manager_diag is not None:
                if not self.sub_control_manager_diag.tracker_status.have_goal:
                    break
        
        for _ in range(3):
            rclpy.spin_once(self, timeout_sec=0.1)

        req_start = Trigger.Request()
        future_start = self.client_start_trjct.call_async(req_start)
        rclpy.spin_until_future_complete(self, future_start)

        if not (future_start.result() and future_start.result().success):
            print(cf.red('O MRS rejeitou o comando de START da trajetória.'))
            return False
        
        tolerancia_metros = 0.25
        while rclpy.ok():
            rclpy.spin_once(self, timeout_sec=0.1) # Mantém a telemetria atualizada

            if self.telem['x'] != 0.0 or self.telem['y'] != 0.0:
                distancia = math.sqrt(
                    (self.telem['x'] - x_global)**2 + 
                    (self.telem['y'] - y_global)**2 + 
                    (self.telem['z'] - z_global)**2
                )

                if distancia < tolerancia_metros:
                    break

        print(cf.blue(f'Navigate finalizado'))
        return True

    def navigateReference(self, x=0, y=0, z=0, yaw=0, speed='slow', frame='uav1/fixed_origin'):

        None

    def land(self):

        req_land = Trigger.Request()
        future = self.client_land.call_async(req_land)
        rclpy.spin_until_future_complete(self, future)

        return True