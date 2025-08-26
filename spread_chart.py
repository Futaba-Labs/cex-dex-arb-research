from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import finplot as fplt

import sys
import zmq
import zmq.asyncio
import json
import time
import datetime
import pandas as pd
from typing import Dict, Any

fplt.display_timezone = datetime.timezone.utc

# デバッグ用のログ設定
import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Publisher:
    
    def __init__(self, port: int):
        self.port = port
        self.context = zmq.asyncio.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind(f'tcp://*:{port}')
        logger.info(f"Publisher initialized on port {port}")

    async def send(self, data: Dict[str, Any]):
        await self.socket.send_string(json.dumps(data))
        logger.debug(f"Published data: {data}")
        
        
class Subscriber:
    
    def __init__(self, port: int):
        self.port = port
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect(f'tcp://localhost:{port}')
        self.socket.setsockopt_string(zmq.SUBSCRIBE, '')
        logger.info(f"Subscriber initialized on port {port}")
        
    def recv(self):
        try:
            data = self.socket.recv_string(flags=zmq.NOBLOCK)
            logger.debug(f"Received data: {data}")
            return json.loads(data)
        except zmq.Again:
            logger.debug("No data available")
            return None
        except Exception as e:
            logger.error(f"Error receiving data: {e}")
            return None


class Worker(QThread):
    timeout = pyqtSignal(pd.DataFrame)

    def __init__(self, port: int):
        super().__init__()
        
        self.data = []
        self.subscriber = Subscriber(port)
        self.running = True
        logger.info("Worker thread initialized")

    def run(self):
        i = 0
        logger.info("Worker thread started")
        
        while self.running:
            try:
                data = self.subscriber.recv()
                if data is not None:
                    self.data.append([i, data['spread']])
                    i += 1
                    logger.info(f"Added data point {i}: spread={data['spread']}")

                    df = pd.DataFrame(self.data, columns=['Date', 'Spread'])
                    logger.debug(f"DataFrame shape: {df.shape}, last row: {df.iloc[-1] if len(df) > 0 else 'empty'}")
                    self.timeout.emit(df)
                else:
                    logger.debug("No data received, waiting...")
                
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in worker: {e}")
                time.sleep(1)
        
        logger.info("Worker thread stopped")

    def stop(self):
        self.running = False
        logger.info("Worker thread stop requested")


class ChartWindow(QMainWindow):
    
    def __init__(self, port: int):
        super().__init__()

        self.df = None
        self.plot = None
        logger.info("ChartWindow initialized")

        # thread
        self.w = Worker(port)
        self.w.timeout.connect(self.update_data)
        self.w.start()

        # timer: update chart every 0.5 second
        self.timer = QTimer(self)
        self.timer.start(500)
        self.timer.timeout.connect(self.update)

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create finplot widget
        self.ax = fplt.create_plot(init_zoom_periods=100)
        self.axs = [self.ax]
        
        # Add finplot widget to layout
        layout.addWidget(self.ax.vb.win)
        
        self.resize(1200, 600)
        logger.info("ChartWindow setup completed")

    def update(self):
        now = datetime.datetime.now()
        self.statusBar().showMessage(str(now))

        if self.df is not None and len(self.df) > 0:
            logger.debug(f"Updating chart with {len(self.df)} data points")
            if self.plot is None:
                logger.info("Creating new plot")
                self.plot = fplt.plot(self.df, ax=self.ax)
                fplt.show(qt_exec=False)
            else:
                logger.debug("Updating existing plot")
                self.plot.update_data(self.df)
        else:
            logger.debug("No data available for chart update")

    @pyqtSlot(pd.DataFrame)
    def update_data(self, df):
        logger.info(f"Received DataFrame update: shape={df.shape}")
        self.df = df
        
    def closeEvent(self, event):
        logger.info("ChartWindow closing, stopping worker thread")
        self.w.stop()
        self.w.wait()
        event.accept()
        
        
# Sample publisher function for test
def send_data(port: int):
    import asyncio
    
    async def _send():
        pub = Publisher(port)
        i = 0
        logger.info("Publisher started, sending test data")
        while True:
            await pub.send({'spread': i})
            i += 1
            await asyncio.sleep(0.5)
            
    asyncio.run(_send())


if __name__ == "__main__":
    from multiprocessing import Process
    
    port = 9999
    
    # テスト用のパブリッシャーを起動
    logger.info("Starting test publisher process")
    p = Process(target=send_data, args=(port,))
    p.start()
    
    logger.info("Starting main application")
    app = QApplication(sys.argv)
    window = ChartWindow(port)
    window.show()
    
    try:
        logger.info("Application started, entering main loop")
        app.exec()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    finally:
        logger.info("Stopping publisher process")
        p.terminate()
        p.join()
        logger.info("Application shutdown complete")