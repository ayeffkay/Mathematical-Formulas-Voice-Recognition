import sys
import shlex
import re
import pandas as pd
from os import path, remove
from sqlalchemy import create_engine
from PyQt5.QtCore import Qt, QProcess
from PyQt5.QtGui import QTextDocument, QTextCursor, QPixmap
from PyQt5.QtWidgets import QApplication, QWidget, QGridLayout,\
    QDesktopWidget, QLabel, QScrollArea, QPlainTextEdit, QStatusBar, QSlider


class SpeechProcessing:
    def __init__(self, text_edit):
        self.queue = []  # распознанные слова
        self.exp = pd.DataFrame()  # словарь ожидаемых слов
        self.mem = ''  # строка из слов self.queue, которые проверяются на "ожидаемость"
        self.kind = ''  # категория ключевого слова
        self.basic_notation = ''  # команда tex для него
        self.pos = 0  # указатель на позицию текущего обрабатываемого слова в self.queue
        self.inside = 0  # указатель, что курсор находится внутри каких-то скобок
        self.constraint = []  # слово-ограничитель
        self.constraint_kind = []  # категория слова-ограничителя
        self.keywords, self.conditions, self.constraints = self.extract_data(self)  # данные из базы
        self.text = text_edit  # редактируемое текстовое поле, в которое будут добавляться команды TEX

    @staticmethod
    def extract_data(self):  # копирование данных из базы
        usr = ''
        passw = ''
        engine = create_engine('mysql+mysqlconnector://{0}:{1}@localhost/TEX'.format(usr, passw))
        keywords = pd.read_sql_table('keywords', engine)
        conditions = pd.read_sql_table('conditions', engine)
        constraints = pd.read_sql_table('constraints', engine)
        return keywords, conditions, constraints

    def new_formula(self):  # встретилась фраза "новая формула"
        del self.queue[:]  # удаляем необработанные слова
        del self.constraint[:]  # удаляем все слова-ограничители
        del self.constraint_kind[:]  # и их категории
        self.mem = ''  # очищаем строку для проверки ожидаемых слов,
        self.kind = ''  # категорию последнего слова,
        self.basic_notation = ''  # команду tex для него,
        self.exp = self.exp[0:0]  # словарь ожидаемых слов,
        self.pos = 0  # ставим указатель на текущеее слово в очереди на начало
        place = QTextCursor(self.text.textCursor())  # получаем копию курсора в редактируемом текстовом поле
        place.movePosition(QTextCursor.EndOfLine)  # перемещаем курсор в конец строки
        self.text.setTextCursor(place)  # устанавливаем новый курсор
        self.text.insertPlainText(' \\\\\n')  # переход на новую строку

    def change_cursor_position(self, value):  # изменение положения курсора в текстовом поле
        if pd.notnull(value):  # если указано перемещение курсора
            place = QTextCursor(self.text.textCursor())  # запоминаем копию текущего курсора
            place.setPosition(place.position() + int(value))  # изменяем позицию курсора на value
            self.text.setTextCursor(place)  # устанавливаем новый курсор
            if value < 0:  # запоминаем переход внутрь скобок
                self.inside = -value
            else:
                self.inside = 0

    def check_expected(self):  # проверка текущего слова на соответствие ожидаемым
        part_match = False  # частичное совпадение
        self.mem += self.queue[self.pos]  # на случай, если ожидается строка из нескольких слов
        match = self.exp.query('following in @self.mem')  # проверяем на точное совпадение наличие слова в словаре
        if not match.empty:  # найдено точное совпадение
            # ожидаемое слово изменяет предыдущую команду tex, удаляем ее("плюс минус", "больше равно" и т.д.)
            if pd.notnull(match.iloc[0][5]):
                # "сумма по модулю", "корень степени" - перед удалением нужно выйти за пределы напечатанных скобок
                # так как курсор уже находится внутри скобок и правая скобка иначе не будет удалена
                if self.inside:
                    self.change_cursor_position(self.inside)
                place = QTextCursor(self.text.textCursor())  # получаем копию текущего курсора
                # выделяем справа налево кол-во символов, которое необходимо удалить
                place.movePosition(QTextCursor.Left,
                                   QTextCursor.KeepAnchor,
                                   int(match.iloc[0][5]))
                place.removeSelectedText()  # удаляем выделенное количество символов
                self.text.setTextCursor(place)  # меняем позицию курсора
            if match.iloc[0][4]:  # есть команда tex с учетом ожидаемых слов, выводим ее
                self.text.insertPlainText(match.iloc[0][4])
            if pd.notnull(match.iloc[0][7]):  # нужно изменить позицию курсора
                self.change_cursor_position(match.iloc[0][7])
            if match.iloc[0][6]:  # есть слово-ограничитель
                self.constraint.append(match.iloc[0][6])  # запоминаем его
                self.constraint_kind.append(self.kind)  # и его категорию
            # удаляем это ожидаемое слово(группу слов) из словаря, так как они больше не нужны
            self.exp = self.exp[self.exp.following != self.mem]
        # проверяем на частичное совпадение, возможно, дальше могут ожидаться другие слова
        # ("сумма по", "сумма по модулю")
        if not (self.exp.empty or self.exp[self.exp.following.str.contains(self.mem)].empty):
            part_match = True  # частичное совпадение
            # добавляем пробел в строку поиска, так как в нее будут добавляться слова на след. итерации
            self.mem += ' '
        if not match.empty or part_match:  # было частичное или полное совпадение
            del self.queue[:self.pos + 1]  # удаляем обработанные слова из очереди, они больше не нужны
            self.pos = 0  # устанавливаем указатель очереди на начало
        # слово не соответствует ожидаемым, позиция при этом не изменяется
        # слово будет проверяться дальше по таблице ключевых слов
        if not part_match:
            self.mem = ''  # очищаем строку проверяемых слов
            self.exp = self.exp[0:0]  # очищаем словарь

    def check_constraint(self):  # извлекаем информацию для слова-ограничителя
        # получаем характеристики для данного огр.слова
        q = self.constraints.query\
            ('constraint_word in @self.constraint[-1] & kind in @self.constraint_kind[-1]')
        if not q.empty:
            # удаляем последний ограничитель из списка слов, считается уже обработанным
            self.queue.remove(self.constraint[-1])
            self.pos = 0
            if q.iloc[0][2]:  # для ограничивающего слова есть команда tex
                self.change_cursor_position(self.inside)  # выходим из скобок
                self.text.insertPlainText(q.iloc[0][2])  # добавляем в вывод команду tex
            if pd.notnull(q.iloc[0][3]):  # необходимо переместить курсор
                self.change_cursor_position(q.iloc[0][3])
            if q.iloc[0][4]:  # есть вложенное ограничение, категория при этом не изменяется
                self.constraint[-1] = q.iloc[0][4]
            else:  # для слова-ограничителя больше нет полезной информации, удаляем его
                del self.constraint[-1]
                del self.constraint_kind[-1]

    def is_key(self, word):
        # проверяем, является ли слово ключевым, находим его категорию и команду tex
        q = self.keywords.query('keyword in @word')
        if not q.empty:  # ключевое слово
            self.basic_notation = q.iloc[0][1]  # команда tex
            self.kind = q.iloc[0][2]  # категория слова
            return True
        return False

    def check_prev(self):  # проверяем наличие предшествующих слов для ключевого слова
        if self.pos > 0:  # в очереди больше одного слова
            # делаем запрос учитывая возможное предыдущее слово
            word = self.queue[self.pos - 1]
            # запоминаем результат в словаре ожидаемых слов
            self.exp = self.exp.append(self.conditions.query('kind in @self.kind & previous in @word'))
            if not self.exp.empty:
                # может быть несколько совпадающих полей для предыдущих слов одной категории
                # но в этом случае команды tex совпадают/полностью зависят от ожидаемых слов
                # поэтому можно обрабатывать только первую строку от запроса
                not1 = self.exp.iloc[0][2]  # запоминаем обозначение с учетом предыдущего слова
                if re.search(r'(буква)+', self.kind):  # встретилась какая-то из заглавных букв
                    not1 = self.to_uppercase(self.basic_notation)  # преобразуем в зависимости от категории буквы
                # если есть обозначение с учетом предыдущего слова, добавляем его в вывод
                # иначе добавляем основное обозначение, если нет и такого обозначения, не добавляем ничего
                self.text.insertPlainText(not1) if not1 \
                    else (self.text.insertPlainText(self.basic_notation) if self.basic_notation else {})
        if self.pos == 0 or self.exp.empty:  # пустое поле предыдущих слов
            # запрос с пустым полем предыдущих слов
            self.exp = self.exp.append(self.conditions.query('kind in @self.kind & previous.isnull()'))
            if self.basic_notation:
                self.text.insertPlainText(self.basic_notation)
        del self.queue[:self.pos + 1]  # удаляем обработанные слова
        self.pos = 0

    def to_uppercase(self, letter):
        if self.kind == 'лат_буква':
            return letter.upper()
        elif self.kind == 'греч_буква':
            letter = re.sub(r'[\\ ]', '', letter)
            up = {'alpha': 'A', 'beta': 'B', 'varepsilon': 'E', 'zeta': 'Z',
                  'eta': 'H', 'iota': 'I', 'kappa': 'K', 'mu': 'M', 'nu': 'N',
                  'o': 'O', 'rho': 'P', 'tau': 'T', 'chi': 'X'}
            return up.get(letter)
        return letter[:1] + letter[1].upper() + letter[2:]

    def remember_following(self):
        if not self.exp.empty:
            no_fol = self.exp[self.exp.following.isnull()]  # строка с пустым полем след.слов
            if not no_fol.empty \
                    and pd.notnull(no_fol.iloc[0][7]):  # но есть характеристики, влияющие на вывод
                self.change_cursor_position(no_fol.iloc[0][7])
                if no_fol.iloc[0][6]:  # присутствует слово-ограничитель
                    self.constraint.append(no_fol.iloc[0][6])  # запоминаем это слово
                    self.constraint_kind.append(self.kind)  # и его категорию
            self.exp = self.exp[self.exp.following.notnull()]  # оставляем только строки с ненулевыми следующими словами

    def parsing(self):  # анализ распознанного текста
        while self.pos < len(self.queue):  # пока не обработаются все полученные на данный момент слова
            while not self.exp.empty and self.pos < len(self.queue):  # ожидаются какие-то слова
                self.check_expected()  # проверка соответствия текущего слова ожидаемому и извлечение информации
            # встретилось слово ограничитель
            if self.constraint and self.pos < len(self.queue) and self.queue[self.pos] == self.constraint[-1]:
                self.check_constraint()
            # дополнительно проверяем, не вышел ли указатель за пределы списка полученных слов,
            # так как на предыдущих этапах значение указателя могло выйти за пределы self.queue
            if self.pos < len(self.queue):
                if self.is_key(self.queue[self.pos]):  # слово является ключом
                    self.check_prev()  # проверяем предыдущие слова
                    self.remember_following()  # составляем словарь ожидаемых слов
                else:
                    self.pos += 1  # переходим к следующему слову


class MainWindow(QWidget):
    def __init__(self, width, height):
        super().__init__()
        self.resize(width, height)  # устанавливаем размер окна по размеру экрана
        self.setWindowTitle('FormulaVoiceInput')  # заголовок

        self.tex = QPlainTextEdit()  # редактируемое текстовое поле, в котором будут выводиться команды TEX
        self.set_tex()  # настройка начального текста, необходимого для компиляции из tex в pdf

        self.image = QLabel()  # здесь выводится картинка с формулой
        self.pixmap = QPixmap()  # пиксельная карта для картинки
        self.scale = 1  # текущий к-т масштабирования картинки
        self.scroll = QScrollArea()  # область с полосами прокрутки

        self.slider = QSlider(Qt.Horizontal)  # ползунок для изменения масштаба
        self.set_slider()

        self.status_bar = QStatusBar()  # нижняя строка состояния
        self.status_bar.addWidget(self.slider)  # добавляем ползунок для изменения масштаба
        self.grid = QGridLayout()  # макет сетки для виджетов
        self.set_layout()  # установка макета

        self.words = SpeechProcessing(self.tex)  # для обработки распознанной речи
        self.subprocess = QProcess(self)  # подпроцесс для получения текста из pocketsphinx
        self.speech_to_text()  # распознавание речи

        self.show()

    def set_tex(self):
        # начальная строка
        start_line = "\\documentclass{article}\n\
\\usepackage[left=0mm,right=0mm,top=0mm,bottom=0mm,bindingoffset=0mm]{geometry}\n\
\\usepackage[fleqn]{amsmath}\n\
\\begin{document}\n\
\\begin{gather*}\n\n\
\\end{gather*}\n\
\\end{document}"
        self.tex.insertPlainText(start_line)  # вставка начальной строки
        self.tex.find('begin{gather*}',
                      QTextDocument.FindBackward)  # находим место фрагмента begin{gather*}
        self.tex.moveCursor(QTextCursor.Down)  # устанавливаем курсор внутри

    def set_slider(self):
        self.slider.setMinimum(0)  # минимальный масштаб
        self.slider.setMaximum(200)  # максимальный масштаб
        self.slider.setValue(100)  # устанавливаем ползунок посередине
        self.slider.valueChanged[int].\
            connect(self.scale_img)  # обработчик изменений положения ползунка

    def scale_img(self, scale):  # масштабирование картинки с формулой
        self.scale = scale / 100
        self.image = QLabel()  # создаем новый виджет для картинки
        # устанавливаем масштабированную картинку
        self.image.setPixmap(self.pixmap.scaledToWidth(self.pixmap.size().width() * self.scale))
        self.scroll.setWidget(self.image)  # добавляем новый виджет в область прокрутки

    def set_layout(self):
        self.grid.addWidget(self.tex, 1, 0)
        self.grid.setSpacing(20)
        self.grid.addWidget(self.scroll, 1, 1)
        self.grid.addWidget(self.status_bar, 2, 1)
        self.setLayout(self.grid)  # устанавливаем макет сетки для окна

    def speech_to_text(self):  # распознавание речи с микрофона с помощью pocketsphinx
        logs = open('speech/pocketsphinx_logs', 'w')  # создаем файл, в который будут записываться логи от pocketsphinx
        cmd = "pocketsphinx_continuous\
        -hmm speech/map \
        -dict speech/math.dict \
        -jsgf speech/math.jsgf \
        -logfn speech/pocketsphinx_logs \
              -inmic yes"
        args = shlex.split(cmd)
        self.subprocess.\
            readyReadStandardOutput.connect(self.stdout_ready)
        self.subprocess.start(args[0], args[1:])

    def stdout_ready(self):
        # меняем кодировку текста, полученного в рез-те распознавания
        text = bytearray(self.subprocess.readAllStandardOutput()).decode("utf-8").rstrip()
        if text == 'новая формула':
            self.words.new_formula()
        elif text == 'обновить':
            self.create_img()
            self.update_img()
        else:
            self.words.queue.extend(text.split())  # добавляем новые слова
            self.words.parsing()  # анализ распознанных слов
            self.create_img()
            self.update_img()

    def create_img(self):  # получение pdf из файла tex
        tex_file = open('tex_file.tex', 'w')  # создаем файл tex_file.tex
        tex_file.write(self.tex.toPlainText())  # запись текста из self.tex в tex_file
        tex_file.close()
        self.start_subprocess('pdflatex tex_file.tex', 1000)
        if path.isfile('tex_file.pdf'):
            self.start_subprocess('pdftoppm -png tex_file.pdf formula', 500)

    # запуск подпроцесса с параметрами, указанными в cmd и временем ожидания завершения delay(в миллисекундах)
    def start_subprocess(self, cmd, delay):
        args = shlex.split(cmd)
        p = QProcess(self)
        p.start(args[0], args[1:])
        p.waitForFinished(delay)
        p.close()

    # загрузка новой картинки при добавлении новых символов
    def update_img(self):
        if path.isfile('formula-1.png'):
            self.pixmap.load('formula-1.png')
            self.image = QLabel()
            w = self.pixmap.size().width()
            self.image.setPixmap(self.pixmap.scaledToWidth(w * self.scale))
            self.scroll.setWidget(self.image)


def exit_handler():  # действия при выходе из приложения
    # прерываем pocketsphinx
    ex.subprocess.close()
    # удаляем временные файлы
    if path.isfile('tex_file.tex'):
        remove('tex_file.tex')
    if path.isfile('tex_file.pdf'):
        remove('tex_file.pdf')
    if path.isfile('tex_file.aux'):
        remove('tex_file.aux')
    if path.isfile('tex_file.dvi'):
        remove('tex_file.dvi')
    if path.isfile('tex_file.log'):
        remove('tex_file.log')
    if path.isfile('formula-1.png'):
        remove('formula-1.png')
    if path.isfile('speech/pocketsphinx_logs'):
        remove('speech/pocketsphinx_logs')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    scr_dim = QDesktopWidget().screenGeometry()  # размеры экрана
    ex = MainWindow(scr_dim.width() / 2, scr_dim.height() / 2)
    app.aboutToQuit.connect(exit_handler)
    sys.exit(app.exec_())
