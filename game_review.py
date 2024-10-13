'''
這個程式是一個功能強大的西洋棋分析工具，包含了走法分析與 PGN 分析等多種功能。

此程式的主要目的是為了讓無法使用 chess.com 付費功能 [game review] 的用戶，提供一個免費、開源且優秀（甚至可能更好）的替代方案。

功能特點：

- **PGN 文件載入與解析**：可以從文件中載入 PGN，或直接在程式中貼上 PGN 文字。
- **走法分析**：使用強大的 Stockfish 引擎對每一步走法進行分析，評估玩家的走法品質。
- **走法分類**：根據評估差異，將走法分類為 "Brilliant"、"Great"、"Best"、"Excellent"、"Good"、"Inaccuracy"、"Mistake"、"Blunder" 等。
- **即時分析**：提供實時的走法評估和主變例顯示，方便玩家理解當前局面的優劣。
- **圖形化介面**：採用 PyQt5 架構，提供友好的使用者介面，包含棋盤顯示與操作。
- **走法導航**：可以使用按鈕或鍵盤方向鍵進行走法的前進與回退。
- **走法輸入**：除了分析 PGN 外，還可以在棋盤上直接進行走子，程式將即時評估該走法。

使用說明：

1. **啟動程式**：執行程式後，將會看到主界面。
2. **載入 PGN**：點擊「載入 PGN 文件」按鈕，選擇您要分析的 PGN 文件，或者在下方的文本框中直接粘貼 PGN 文字。
3. **開始分析**：點擊「分析」按鈕，程式將開始對 PGN 進行解析和分析。請耐心等待，分析過程可能需要一些時間。
4. **查看分析結果**：分析完成後，您可以使用「上一手」和「下一手」按鈕（或鍵盤方向鍵）瀏覽每一步的分析結果。左側將顯示棋盤狀態，右側顯示評估資訊和走法類型。
5. **即時分析**：在棋盤上點擊並移動棋子，可以嘗試不同的走法，程式將即時給出評估。
6. **評估類型顯示**：程式將根據走法的好壞，給出相應的評估類型，並以不同的顏色標示。

注意事項：

- **引擎設定**：請確保您已經安裝了 Stockfish 引擎，並在程式中正確設定了引擎的路徑（路徑應放在程式的第626行)。如果您的引擎路徑不同，請修改程式中的 `self.engine_path`。
- **性能需求**：程式在分析時可能會佔用較多的系統資源，特別是在設定較高的深度時。

本程式提供了一個強大而靈活的西洋棋分析工具，對於想要深入了解自己對局、提升棋藝的玩家而言，將是一個不可或缺的好幫手。歡迎使用並提供反饋！
'''
import sys
import os
import io
import threading
import uuid  # 用於生成唯一的線程標識符
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton,
    QTextEdit, QFileDialog, QMessageBox, QHBoxLayout, QGraphicsView, QGraphicsScene, QLabel
)
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QFont
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QRectF, QThread
from PyQt5 import QtCore
import chess
import chess.engine
import chess.pgn


class Worker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(object)
    analysis_data = []

    def __init__(self, pgn_text, engine_path):
        super().__init__()
        self.pgn_text = pgn_text
        self.engine_path = engine_path
        # 初始化引擎實例，避免多次啟動和關閉引擎
        self.engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
        self.engine.configure({"Threads": 2, "Hash": 128})

    def run(self):
        try:
            game = chess.pgn.read_game(io.StringIO(self.pgn_text))
            if not game:
                self.progress.emit("無效的 PGN，請檢查您的輸入。")
                self.finished.emit()
                return
        except Exception as e:
            self.progress.emit(f"解析 PGN 時發生錯誤：{e}")
            self.finished.emit()
            return

        board = game.board()
        node = game
        move_number = 1

        # 存儲每一步的數據，以便後續導航
        self.analysis_data = []

        while not node.is_end():
            next_node = node.next()
            if not next_node:
                break
            move = next_node.move
            san_move = board.san(move)  # 在推進前取得 SAN

            # 確定當前走棋方
            player = '白方' if board.turn == chess.WHITE else '黑方'

            # 保存走棋前的棋盤狀態
            board_before_move = board.copy()

            # 評估當前局面，獲取最佳走法和評估
            info = self.engine.analyse(board_before_move, chess.engine.Limit(depth=18), multipv=3)

            # 獲取所有變體的排序
            variations = []
            for entry in info:
                if "multipv" in entry:
                    pv_number = entry["multipv"]
                    move_sequence = entry["pv"]
                    score = entry["score"].white().score(mate_score=100000)
                    variations.append((pv_number, move_sequence, score))
            # 按照 multipv 順序排序
            variations.sort(key=lambda x: x[0])

            # 提取最佳走法和第二選擇
            if len(variations) >= 2:
                best_move = variations[0][1][0]
                best_score = variations[0][2]
                second_best_move = variations[1][1][0]
                second_best_score = variations[1][2]
            elif len(variations) == 1:
                best_move = variations[0][1][0]
                best_score = variations[0][2]
                second_best_move = None
                second_best_score = best_score
            else:
                # 如果沒有獲取到變體，使用引擎的推薦走法
                result = self.engine.play(board_before_move, chess.engine.Limit(depth=18))
                best_move = result.move
                best_score = None
                second_best_move = None
                second_best_score = None

            # 評估玩家的實際走法
            board_before_move.push(move)
            info_after = self.engine.analyse(board_before_move, chess.engine.Limit(depth=18))
            eval_after = info_after.get('score')
            if eval_after is not None:
                eval_after = eval_after.white()
                move_score = eval_after.score(mate_score=100000)
            else:
                move_score = None
            board_before_move.pop()  # 恢復棋盤

            # 計算與最佳走法的評估差
            if best_score is not None and move_score is not None:
                eval_diff = move_score - best_score
            else:
                eval_diff = 0

            # 對於黑方，需要將評估差值取反
            if player == '黑方':
                eval_diff = -eval_diff

            # 分類走法
            eval_type = self.categorize_move(
                board_before_move, move, best_move, second_best_move, eval_diff
            )

            # 獲取評估分數，直接輸出 Stockfish 的評估，不做任何調整
            eval_score = eval_after

            # 處理將殺的情況
            if eval_score is not None and eval_score.is_mate():
                mate_in = eval_score.mate()
                eval_score_display = f"將殺於 {mate_in}"
            elif eval_score is not None:
                cp = eval_score.score()
                if cp is not None:
                    eval_score_display = f"{cp / 100:.2f}"
                else:
                    eval_score_display = "未知"
            else:
                eval_score_display = "未知"

            # 推進棋盤到下一狀態
            board.push(move)

            # 格式化輸出
            if player == '白方':
                output = f"{move_number}. {san_move} ({player}): {eval_type} (評估: {eval_score_display})"
            else:
                output = f"{move_number}... {san_move} ({player}): {eval_type} (評估: {eval_score_display})"
                move_number += 1  # 黑方走完才增加回合數

            # 存儲這一步的數據，確保包含 'eval_type'
            self.analysis_data.append({
                'board': board.copy(),
                'output': output,
                'move_number': move_number - 1 if player == '黑方' else move_number,
                'player': player,
                'san_move': san_move,
                'eval_type': eval_type,  # 包含 eval_type
                'eval_score': eval_score_display
            })

            # 發送進度更新
            self.progress.emit(output)

            node = next_node

        self.engine.quit()
        self.finished.emit()

    def categorize_move(self, board_before_move, move, best_move, second_best_move, eval_diff):
        # 與之前相同的分類方法
        if move == best_move:
            score_diff = self.get_move_score(board_before_move.copy(), best_move) - self.get_move_score(board_before_move.copy(), second_best_move) if second_best_move else 0
            if second_best_move and score_diff > 200:
                if self.is_intuitive(board_before_move, move):
                    return "Best"
                else:
                    if self.is_sacrifice(board_before_move, move):
                        return "Brilliant"
                    else:
                        return "Great"
            else:
                return "Best"
        else:
            if move == second_best_move and abs(eval_diff) <= 30:
                return "Excellent"
            elif abs(eval_diff) <= 50:
                return "Good"
            elif abs(eval_diff) <= 90:
                return "Inaccuracy"
            elif abs(eval_diff) <= 300:
                return "Mistake"
            else:
                return "Blunder"

    def get_move_score(self, board, move):
        # 獲取指定走法的評估分數
        board.push(move)
        info = self.engine.analyse(board, chess.engine.Limit(depth=18))
        score = info.get('score')
        if score is not None:
            score = score.white().score(mate_score=100000)
        else:
            score = 0
        board.pop()
        return score

    def is_intuitive(self, board, move):
        # 檢查是否為直覺走法
        piece = board.piece_at(move.from_square)
        if piece is None:
            return False

        piece_type = piece.piece_type
        if piece_type in [chess.KNIGHT, chess.BISHOP, chess.PAWN]:
            from_rank = chess.square_rank(move.from_square)
            to_rank = chess.square_rank(move.to_square)
            if piece.color == chess.WHITE and to_rank > from_rank:
                return True
            elif piece.color == chess.BLACK and to_rank < from_rank:
                return True

        return False

    def is_sacrifice(self, board, move):
        # 判斷是否為棄子
        piece_value = {
            chess.PAWN: 1,
            chess.KNIGHT: 3,
            chess.BISHOP: 3,
            chess.ROOK: 5,
            chess.QUEEN: 9,
            chess.KING: 0
        }
        piece = board.piece_at(move.from_square)
        captured_piece = board.piece_at(move.to_square)
        if piece and captured_piece:
            if piece_value[piece.piece_type] > piece_value[captured_piece.piece_type]:
                return True
        return False

class AnalysisWorker(QObject):
    analysis_updated = pyqtSignal(str)

    def __init__(self, board, engine_path, parent=None):
        super().__init__(parent)
        self.board = board.copy()
        self.engine_path = engine_path
        self.is_running = True
        self.engine = None

    def run(self):
        depth = 30 # 最大深度
        eval_str = "未知"
        pv_moves = ""
        self.engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
        
        try:
            self.engine.configure({"Threads": 2, "Hash": 128})
            # 使用 PVS 增量加深
            for current_depth in range(1, depth + 1):
                if not self.is_running:
                    break
                try:
                    info = self.engine.analyse(self.board, chess.engine.Limit(depth=current_depth))
                    # 實時更新評估
                    score = info.get('score')
                    if score is not None:
                        score = score.white()
                        if score.is_mate():
                            eval_str = f"將殺於 {score.mate()}"
                        else:
                            eval_str = f"{score.score() / 100:.2f}"
                    else:
                        eval_str = "未知"

                    pv = info.get('pv', [])
                    if pv:
                        # 使用臨時棋盤來生成 SAN 表示
                        temp_board = self.board.copy()
                        pv_moves_list = []
                        for move in pv:
                            try:
                                san_move = temp_board.san(move)
                            except Exception as e:
                                san_move = temp_board.uci(move)
                            pv_moves_list.append(san_move)
                            temp_board.push(move)
                        pv_moves = ' '.join(pv_moves_list)
                    else:
                        pv_moves = ''

                    output = f"深度 {current_depth}: 評估 {eval_str}, 主變例: {pv_moves}"
                    self.analysis_updated.emit(output)

                except Exception as e:
                    # 處理分析中的任何異常
                    eval_str = "分析失敗"
                    pv_moves = ''
                    print(f"引擎分析在深度 {current_depth} 失敗：{e}")
                    break
        finally:
            if self.engine:
                self.engine.quit()
                self.engine = None                

    def stop(self):
        self.is_running = False
        if self.engine:
            self.engine.quit()
            self.engine = None




class MoveTypeWorker(QObject):
    finished = pyqtSignal(str, str)  # 添加一個參數，用於傳遞線程ID

    def __init__(self, board_before_move, move, engine_path, thread_id, parent=None):
        super().__init__(parent)
        self.board_before_move = board_before_move
        self.move = move
        self.engine_path = engine_path
        self.thread_id = thread_id  # 儲存線程ID
        self.engine = None
        
    def run(self):
        # 執行評估的邏輯
        with chess.engine.SimpleEngine.popen_uci(self.engine_path) as engine:
            engine.configure({"Threads": 2, "Hash": 128})

            # 獲取最佳走法和評估
            info = engine.analyse(self.board_before_move, chess.engine.Limit(depth=18), multipv=3)

            # 獲取所有變體的排序
            variations = []
            for entry in info:
                if "multipv" in entry:
                    pv_number = entry["multipv"]
                    move_sequence = entry["pv"]
                    score = entry["score"].white().score(mate_score=100000)
                    variations.append((pv_number, move_sequence, score))
            # 按照 multipv 順序排序
            variations.sort(key=lambda x: x[0])

            # 提取最佳走法和第二選擇
            if len(variations) >= 2:
                best_move = variations[0][1][0]
                best_score = variations[0][2]
                second_best_move = variations[1][1][0]
                second_best_score = variations[1][2]
            elif len(variations) == 1:
                best_move = variations[0][1][0]
                best_score = variations[0][2]
                second_best_move = None
                second_best_score = best_score
            else:
                # 如果沒有獲取到變體，使用引擎的推薦走法
                result = engine.play(self.board_before_move, chess.engine.Limit(depth=18))
                best_move = result.move
                best_score = None
                second_best_move = None
                second_best_score = None

            # 評估玩家的實際走法
            self.board_before_move.push(self.move)
            info_after = engine.analyse(self.board_before_move, chess.engine.Limit(depth=18))
            eval_after = info_after.get('score')
            if eval_after is not None:
                eval_after = eval_after.white()
                move_score = eval_after.score(mate_score=100000)
            else:
                move_score = None
            self.board_before_move.pop()  # 恢復棋盤

            # 計算與最佳走法的評估差
            if best_score is not None and move_score is not None:
                eval_diff = move_score - best_score
            else:
                eval_diff = 0

            # 確定當前走棋方
            player = '白方' if self.board_before_move.turn == chess.WHITE else '黑方'

            # 對於黑方，需要將評估差值取反
            if player == '黑方':
                eval_diff = -eval_diff

            # 分類走法
            eval_type = self.categorize_move(
                self.board_before_move, self.move, best_move, second_best_move, eval_diff
            )

            # 發射信號，傳遞評估類型和線程ID
            self.finished.emit(eval_type, self.thread_id)

    def categorize_move(self, board_before_move, move, best_move, second_best_move, eval_diff):
        # 與之前相同的分類方法
        if move == best_move:
            score_diff = self.get_move_score(board_before_move.copy(), best_move) - self.get_move_score(board_before_move.copy(), second_best_move) if second_best_move else 0
            if second_best_move and score_diff > 200:
                if self.is_intuitive(board_before_move, move):
                    return "Best"
                else:
                    if self.is_sacrifice(board_before_move, move):
                        return "Brilliant"
                    else:
                        return "Great"
            else:
                return "Best"
        else:
            if move == second_best_move and abs(eval_diff) <= 30:
                return "Excellent"
            elif abs(eval_diff) <= 50:
                return "Good"
            elif abs(eval_diff) <= 90:
                return "Inaccuracy"
            elif abs(eval_diff) <= 300:
                return "Mistake"
            else:
                return "Blunder"

    def get_move_score(self, board, move):
        # 獲取指定走法的評估分數
        board.push(move)
        try:
            with chess.engine.SimpleEngine.popen_uci(self.engine_path) as engine:
                engine.configure({"Threads": 2, "Hash": 128})
                info = engine.analyse(board, chess.engine.Limit(depth=18))
                score = info.get('score')
                if score is not None:
                    score = score.white().score(mate_score=100000)
                else:
                    score = 0
        except Exception as e:
            score = 0
            print(f"獲取走法評估失敗：{e}")
        board.pop()
        return score

    def is_intuitive(self, board, move):
        # 檢查是否為直覺走法
        piece = board.piece_at(move.from_square)
        if piece is None:
            return False

        piece_type = piece.piece_type
        if piece_type in [chess.KNIGHT, chess.BISHOP, chess.PAWN]:
            from_rank = chess.square_rank(move.from_square)
            to_rank = chess.square_rank(move.to_square)
            if piece.color == chess.WHITE and to_rank > from_rank:
                return True
            elif piece.color == chess.BLACK and to_rank < from_rank:
                return True

        return False

    def is_sacrifice(self, board, move):
        # 判斷是否為棄子
        piece_value = {
            chess.PAWN: 1,
            chess.KNIGHT: 3,
            chess.BISHOP: 3,
            chess.ROOK: 5,
            chess.QUEEN: 9,
            chess.KING: 0
        }
        piece = board.piece_at(move.from_square)
        captured_piece = board.piece_at(move.to_square)
        if piece and captured_piece:
            if piece_value[piece.piece_type] > piece_value[captured_piece.piece_type]:
                return True
        return False
    def stop(self):
        if self.engine:
            self.engine.quit()
            self.engine = None

class ChessBoardWidget(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.board = chess.Board()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.square_size = 80  # 每個格子的大小
        self.selected_square = None  # 選中的格子
        self.valid_moves = []  # 選中棋子的合法走法
        self.load_images()
        self.draw_board()

        # 新增的代碼
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFixedSize(self.square_size * 8, self.square_size * 8)
        self.setSceneRect(0, 0, self.square_size * 8, self.square_size * 8)

    def sizeHint(self):
        return QtCore.QSize(8 * self.square_size, 8 * self.square_size)

    def load_images(self):
        # 加載棋子圖像
        self.piece_images = {}
        pieces = ['P', 'N', 'B', 'R', 'Q', 'K']
        colors = ['w', 'b']
        for color in colors:
            for piece in pieces:
                filename = f"images/{color}{piece}.png"
                if not os.path.exists(filename):
                    print(f"缺少棋子圖像文件：{filename}")
                    continue
                pixmap = QPixmap(filename)
                self.piece_images[color + piece] = pixmap

    def draw_board(self):
        self.scene.clear()
        colors = [QColor("#F0D9B5"), QColor("#B58863")]
        for rank in range(8):
            for file in range(8):
                square_color = colors[(rank + file) % 2]
                rect = QRectF(file * self.square_size, (7 - rank) * self.square_size, self.square_size, self.square_size)
                self.scene.addRect(rect, QPen(Qt.NoPen), QBrush(square_color))

                # 繪製選中的格子
                square = chess.square(file, rank)
                if self.selected_square == square:
                    self.scene.addRect(rect, QPen(QColor("blue"), 3))

                # 繪製合法走法
                if square in self.valid_moves:
                    self.scene.addEllipse(
                        file * self.square_size + self.square_size / 4,
                        (7 - rank) * self.square_size + self.square_size / 4,
                        self.square_size / 2,
                        self.square_size / 2,
                        QPen(Qt.NoPen),
                        QBrush(QColor(0, 255, 0, 128))
                    )

                # 繪製棋子
                piece = self.board.piece_at(square)
                if piece:
                    piece_symbol = piece.symbol()
                    color = 'w' if piece_symbol.isupper() else 'b'
                    piece_type = piece_symbol.upper()
                    pixmap = self.piece_images.get(color + piece_type)
                    if pixmap:
                        self.scene.addPixmap(pixmap.scaled(self.square_size, self.square_size)).setPos(
                            file * self.square_size, (7 - rank) * self.square_size)

    def mousePressEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        x = scene_pos.x()
        y = scene_pos.y()
        file = int(x // self.square_size)
        rank = 7 - int(y // self.square_size)
        if 0 <= file <= 7 and 0 <= rank <= 7:
            square = chess.square(file, rank)

            if self.selected_square is None:
                # 選中棋子
                piece = self.board.piece_at(square)
                if piece and piece.color == self.board.turn:
                    self.selected_square = square
                    # 獲取合法走法
                    self.valid_moves = [move.to_square for move in self.board.legal_moves if move.from_square == square]
            else:
                # 嘗試移動棋子
                move = chess.Move(self.selected_square, square)
                if move in self.board.legal_moves:
                    self.board.push(move)
                    # 重置「當前走法類型」標籤
                    self.parent_window.reset_move_eval_label()
                    # 停止之前的評估線程
                    self.parent_window.stop_move_type_evaluation()
                    # 評估當前走法
                    self.parent_window.update_analysis()
                    # 評估當前走法
                    self.parent_window.evaluate_current_move(move)
                self.selected_square = None
                self.valid_moves = []
            self.draw_board()

    def set_board(self, board):
        self.board = board.copy()
        self.selected_square = None
        self.valid_moves = []
        self.draw_board()

class PGNAnalyzer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.engine_path = r"D:/python/my chess game code/stockfish/stockfish-windows-x86-64-avx2.exe"
        self.current_move_index = 0
        self.analysis_data = []
        self.move_evaluation = ""  # 當前走法的評估類型

        self.analysis_thread = None  # 實時分析線程
        self.evaluate_thread = None  # 評估當前走法的線程
        self.current_evaluate_thread_id = None  # 用於跟蹤當前活動的評估線程ID
        self.current_move_type_thread_id = None  # 初始化當前走法類型評估線程ID

    def initUI(self):
        self.setWindowTitle('PGN 分析器')
        self.setGeometry(100, 100, 1200, 800)

        # 主佈局
        main_layout = QHBoxLayout()
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setLayout(main_layout)

        # 左側棋盤
        self.chessboard = ChessBoardWidget(self)
        main_layout.addWidget(self.chessboard, stretch=3)

        # 右側佈局
        right_layout = QVBoxLayout()
        main_layout.addLayout(right_layout, stretch=2)

        # 上方實時分析
        self.analysis_output = QTextEdit()
        self.analysis_output.setReadOnly(True)
        right_layout.addWidget(self.analysis_output)

        # 顯示當前走法的評估類型，並放大
        self.move_eval_label = QLabel("當前走法類型：")
        font = QFont()
        font.setPointSize(20)  # 放大字體
        self.move_eval_label.setFont(font)
        right_layout.addWidget(self.move_eval_label)

        # 中間按鈕佈局
        button_layout = QHBoxLayout()
        load_button = QPushButton('載入 PGN 文件')
        load_button.clicked.connect(self.load_pgn_file)
        button_layout.addWidget(load_button)

        analyze_button = QPushButton('分析')
        analyze_button.clicked.connect(self.start_analysis)
        button_layout.addWidget(analyze_button)

        prev_button = QPushButton('上一手')
        prev_button.clicked.connect(self.previous_move)
        button_layout.addWidget(prev_button)

        next_button = QPushButton('下一手')
        next_button.clicked.connect(self.next_move)
        button_layout.addWidget(next_button)

        right_layout.addLayout(button_layout)

        # 下方 PGN 輸入
        self.pgn_input = QTextEdit()
        self.pgn_input.setPlaceholderText("請在此粘貼您的 PGN...")
        right_layout.addWidget(self.pgn_input)

        # 設置焦點策略，確保主窗口可以接收鍵盤事件
        self.setFocusPolicy(Qt.StrongFocus)
        self.installEventFilter(self)

    def load_pgn_file(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(
            self, "選擇 PGN 文件", "", "PGN Files (*.pgn);;All Files (*)", options=options)
        if file_name:
            try:
                with open(file_name, 'r', encoding='utf-8') as f:
                    pgn_content = f.read()
                    self.pgn_input.setText(pgn_content)
            except Exception as e:
                QMessageBox.critical(self, "錯誤", f"無法讀取文件：{e}")

    def start_analysis(self):
        pgn_text = self.pgn_input.toPlainText()
        if not pgn_text.strip():
            QMessageBox.warning(self, "提示", "請先輸入 PGN。")
            return

        # 禁用按鈕，防止重複點擊
        self.set_buttons_enabled(False)
        self.analysis_output.clear()

        # 創建線程並開始分析
        self.worker = Worker(pgn_text, self.engine_path)
        self.thread = threading.Thread(target=self.worker.run)
        self.worker.progress.connect(self.handle_progress)
        self.worker.finished.connect(self.analysis_finished)
        self.thread.start()

    def handle_progress(self, message):
        if isinstance(message, str):
            # 可以在此處更新分析進度
            pass
        else:
            pass  # 處理非字符串的消息

    def analysis_finished(self):
        # 分析完成，啟用按鈕
        self.set_buttons_enabled(True)
        QMessageBox.information(self, "完成", "分析完成！")

        # 獲取分析數據
        self.analysis_data = self.worker.analysis_data
        self.current_move_index = 0

        # 顯示第一個棋盤
        if self.analysis_data:
            self.update_display()

    def set_buttons_enabled(self, enabled):
        for widget in self.findChildren(QPushButton):
            widget.setEnabled(enabled)

    def eventFilter(self, obj, event):
        if event.type() == event.KeyPress:
            if event.key() == Qt.Key_Right:
                self.next_move()
                return True  # 已處理事件
            elif event.key() == Qt.Key_Left:
                self.previous_move()
                return True  # 已處理事件
        return super().eventFilter(obj, event)

    def previous_move(self):
        if self.current_move_index > 0:
            self.current_move_index -= 1
            self.update_display()

    def next_move(self):
        if self.current_move_index < len(self.analysis_data) - 1:
            self.current_move_index += 1
            self.update_display()

    def update_display(self):
        data = self.analysis_data[self.current_move_index]
        self.chessboard.set_board(data['board'])
        self.move_evaluation = data['eval_type']
        self.update_move_eval_label(self.move_evaluation)
        self.update_analysis()

    def update_move_eval_label(self, eval_type):
        # 定義顏色映射
        color_mapping = {
            "Good": "green",
            "Excellent": "green",
            "Best": "green",
            "Great": "green",
            "Brilliant": "green",
            "Inaccuracy": "yellow",
            "Mistake": "orange",
            "Blunder": "red"
        }
        color = color_mapping.get(eval_type, "black")
        # 設置字體大小
        font = self.move_eval_label.font()
        font.setPointSize(20)  # 放大字體
        self.move_eval_label.setFont(font)
        # 設置文本和顏色
        self.move_eval_label.setText(f"<span style='color:{color}'>當前走法類型：{eval_type}</span>")

    def update_analysis(self):
        # 停止之前的分析線程
        if hasattr(self, 'analysis_worker') and self.analysis_thread is not None:
            self.analysis_worker.stop()
            self.analysis_thread.quit()
            self.analysis_thread.wait()
            self.analysis_worker.deleteLater()
            self.analysis_thread = None

        board = self.chessboard.board.copy()

        # 創建分析工作者和線程
        self.analysis_worker = AnalysisWorker(board, self.engine_path)
        self.analysis_thread = QThread()
        self.analysis_worker.moveToThread(self.analysis_thread)
        self.analysis_worker.analysis_updated.connect(self.update_analysis_output)
        self.analysis_thread.started.connect(self.analysis_worker.run)
        self.analysis_thread.start()


    def update_analysis_output(self, output):
        # 實時更新分析輸出，這裡確保不會阻塞主線程
        self.analysis_output.setText(output)

    def evaluate_current_move(self, move):
        board = self.chessboard.board.copy()
        # 撤銷一步以獲取移動前的棋盤
        board.pop()
        board_before_move = board.copy()

        # 生成一個唯一的線程ID
        thread_id = str(uuid.uuid4())
        self.current_evaluate_thread_id = thread_id
        self.current_move_type_thread_id = thread_id  # 更新當前走法類型評估線程ID


        '''# 如果有正在運行的評估線程，停止它
        if hasattr(self, 'evaluate_thread') and self.evaluate_thread is not None:
            # 斷開舊線程的信號連接
            try:
                self.evaluate_worker.finished.disconnect()
            except TypeError:
                pass
            self.evaluate_worker.stop()
            self.evaluate_thread.quit()
            self.evaluate_thread.wait()
            self.evaluate_thread = None
            self.evaluate_worker = None'''

        # 創建新的工作者和線程（不需要再次停止舊線程）
        self.move_type_worker = MoveTypeWorker(board_before_move, move, self.engine_path, thread_id)
        self.move_type_thread = QThread()
        self.move_type_worker.moveToThread(self.move_type_thread)
        self.move_type_worker.finished.connect(self.on_move_type_evaluated)
        self.move_type_thread.started.connect(self.move_type_worker.run)
        self.move_type_thread.start()

    def on_evaluate_finished(self, eval_type, thread_id):
        # 檢查線程ID是否匹配
        if thread_id != self.current_evaluate_thread_id:
            # 如果不匹配，說明這是舊線程的結果，忽略它
            return

        # 在主線程中更新 GUI
        self.update_move_eval_label(eval_type)
        # 清理線程和工作者
        self.evaluate_thread.quit()
        self.evaluate_thread.wait()
        self.evaluate_worker.deleteLater()
        self.evaluate_thread.deleteLater()
        self.evaluate_worker = None
        self.evaluate_thread = None

    def closeEvent(self, event):
        try:
            if hasattr(self, 'worker') and hasattr(self.worker, 'engine'):
                self.worker.engine.quit()
            if hasattr(self, 'analysis_worker') and self.analysis_thread is not None:
                self.analysis_worker.stop()
                self.analysis_thread.quit()
                self.analysis_thread.wait()
            if hasattr(self, 'evaluate_thread') and self.evaluate_thread is not None:
                self.evaluate_worker.stop()
                self.evaluate_thread.quit()
                self.evaluate_thread.wait()
            if hasattr(self, 'move_type_worker') and self.move_type_thread is not None:
                self.move_type_worker.stop()
                self.move_type_thread.quit()
                self.move_type_thread.wait()
        except:
            pass
        event.accept()
    def on_move_type_evaluated(self, eval_type, thread_id):
        # 檢查線程ID是否匹配
        if thread_id != self.current_move_type_thread_id:
            # 如果不匹配，忽略舊線程的結果
            return

        # 更新當前走法類型的顯示
        self.update_move_eval_label(eval_type)

        # 清理線程和工作者
        self.move_type_thread.quit()
        self.move_type_thread.wait()
        self.move_type_worker.deleteLater()
        self.move_type_thread.deleteLater()
        self.move_type_worker = None
        self.move_type_thread = None
    def reset_move_eval_label(self):
        # 重置標籤為預設狀態
        self.move_eval_label.setText("當前走法類型：")
        font = self.move_eval_label.font()
        font.setPointSize(20)  # 設置字體大小
        self.move_eval_label.setFont(font)
        self.move_eval_label.setStyleSheet("")  # 清除樣式
    def stop_move_type_evaluation(self):
        # 如果有正在運行的評估線程，停止它
        if hasattr(self, 'move_type_thread') and self.move_type_thread is not None:
            # 斷開舊線程的信號連接
            try:
                self.move_type_worker.finished.disconnect()
            except TypeError:
                pass
            self.move_type_worker.stop()
            self.move_type_thread.quit()
            self.move_type_thread.wait()
            self.move_type_worker = None
            self.move_type_thread = None


if __name__ == '__main__':
    app = QApplication(sys.argv)
    analyzer = PGNAnalyzer()
    analyzer.show()
    sys.exit(app.exec_())
