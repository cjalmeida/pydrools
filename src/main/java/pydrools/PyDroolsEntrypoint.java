package pydrools;

import java.net.ServerSocket;

import py4j.GatewayServer;

/**
 * PyDroolsEntrypoint
 */
public class PyDroolsEntrypoint {

    public static void main(String[] args) throws Exception {
        ServerSocket socket = new ServerSocket(0);
        int port = socket.getLocalPort();
        socket.close();
        PyDroolsEntrypoint app = new PyDroolsEntrypoint();
        GatewayServer server = new GatewayServer(app, port);
        server.start();
        System.out.println("PyDrools gateway started on port " + port);
        System.out.println("PORT:" + port);
    }

}