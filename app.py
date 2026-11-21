"""Native Qt desktop client for Dope Wars - BFT edition."""
import json
import os
import sys
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QUrl, QPointF, QSize
from PySide6.QtGui import QColor, QFont, QPalette, QFontDatabase, QDesktopServices, QIcon, QPainter, QPixmap, QPolygonF
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QVBoxLayout,
    QHBoxLayout, QGridLayout, QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit,
    QDialog, QDialogButtonBox, QMessageBox, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QProgressBar)
from game import (Game, RuleError, new_game, money, demand, VERSION, RULESET, DRUGS,
                  CITIES, DISTRICTS, area_description, DURATIONS, BAGS, WEAPONS, MULE_TIERS, ASSETS,
                  OBSERVED, SOURCE, LATEST_SOURCE, WASH_OPTIONS, mule_risk)

from visuals import drug_icon

APP_NAME = 'Dope Wars - BFT edition'
from platform_paths import data_dir
DATA = data_dir()
SAVE = DATA / 'save.json'
SCORES = DATA / 'highscores.json'

STYLE = """
* { font-family: "Segoe UI", "Noto Sans", "DejaVu Sans", "Liberation Sans", sans-serif; font-size: 13px; color: #202934; }
QMainWindow, QDialog, QWidget#pageContent { background: #f0f1f3; }
QLabel { background: transparent; }
QLabel[role="muted"] { color: #616b77; }
QLabel[role="title"] { font-size: 20px; font-weight: 600; }
QLabel[role="section"] { font-size: 14px; font-weight: 600; }
QLabel[role="eyebrow"] { font-weight: 600; color: #616b77; }
QFrame#card { background: #fff; border: 1px solid #cbd0d7; border-radius: 4px; }
QLabel#notice { background: #e6ede9; color: #315a49; padding: 7px; border-radius: 4px; }
QToolTip { background: #182127; color: #ffffff; border: none; padding: 7px; }
QLabel[role="profit"] { color: #26724d; }
QLabel[role="loss"] { color: #a23f3f; }
QFrame#brand { background: #182127; border-radius: 4px; }
QFrame#brand QLabel { color: #c4d6cb; padding: 4px; }
QPushButton { background: #fafbfc; border: 1px solid #b8c0ca; border-radius: 4px; padding: 6px 10px; }
QPushButton:hover { background: #e6eef9; border-color: #6889b6; }
QPushButton:pressed { background: #d3e2f5; }
QPushButton:disabled { color: #9299a2; background: #e9ebee; border-color: #d2d6dc; }
QPushButton[role="primary"] { background: #24588c; color: white; border-color: #24588c; }
QPushButton[role="primary"]:disabled { background: #8d9eaf; border-color: #8d9eaf; }
QPushButton[role="danger"] { color: #a32828; }
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit { background: white; border: 1px solid #b8c0ca; border-radius: 3px; padding: 5px; min-height: 20px; }
QComboBox QAbstractItemView { background: #ffffff; color: #202934; selection-background-color: #24588c; selection-color: #ffffff; border: 1px solid #b8c0ca; outline: none; }
QComboBox QAbstractItemView::item { min-height: 26px; padding: 3px 7px; }
QComboBox QAbstractItemView::item:selected { background: #24588c; color: #ffffff; }
QTableWidget { background: white; alternate-background-color: #f6f7f9; border: 1px solid #b8c0ca; selection-background-color: #dbe9fa; selection-color: #163a64; }
QTableWidget::item { padding: 3px; }
QHeaderView::section { background: #e5e8ed; border: none; border-bottom: 1px solid #b8c0ca; padding: 5px; font-weight: 600; }
QScrollArea { border: none; background: transparent; }
QProgressBar { background: #dce2e9; border: 1px solid #b8c0ca; border-radius: 3px; text-align: center; min-height: 18px; }
QProgressBar::chunk { background: #7bb29a; }
QMenuBar, QMenu { background: #f0f1f3; }
QMenu::item:selected { background: #dbe9fa; }
"""


def average_cost(total, quantity):
    # Danish formatting with two decimals, preserving fractional weighted averages.
    return f'{total / quantity:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.') + ' kr.'


def label(text, role=None, wrap=True):
    w = QLabel(str(text))
    w.setTextFormat(Qt.TextFormat.PlainText)
    w.setWordWrap(wrap)
    if role:
        w.setProperty('role', role)
    return w


def button(text, fn, role=None):
    b = QPushButton(text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if role:
        b.setProperty('role', role)
    b.clicked.connect(lambda _=False: fn())
    return b


def row(*widgets):
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    for item in widgets:
        if isinstance(item, int):
            lay.addStretch(item)
        else:
            lay.addWidget(item)
    return w


def card(title=None, subtitle=None):
    w = QFrame()
    w.setObjectName('card')
    lay = QVBoxLayout(w)
    lay.setContentsMargins(12, 12, 12, 12)
    lay.setSpacing(8)
    if title:
        lay.addWidget(label(title, 'section'))
    if subtitle:
        lay.addWidget(label(subtitle, 'muted'))
    return w, lay


def spin(maximum=1_000_000_000, value=1):
    w = QSpinBox()
    w.setRange(1, max(1, min(maximum, 2_000_000_000)))
    w.setValue(value)
    w.setGroupSeparatorShown(True)
    return w


class MoneySpinBox(QDoubleSpinBox):
    def __init__(self, value=1):
        super().__init__();self.setDecimals(0);self.setRange(1,10**12);self.setValue(value);self.setGroupSeparatorShown(True)
    def value(self):return int(super().value())
    def maximum(self):return int(super().maximum())


def table(headers, rows, height=None):
    t = QTableWidget(len(rows), len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().hide()
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setShowGrid(False)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.verticalHeader().setDefaultSectionSize(30)
    for i, values in enumerate(rows):
        for j, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            if j:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            t.setItem(i, j, item)
    if height:
        t.setFixedHeight(height)
    return t


class StartDialog(QDialog):
    def __init__(self, parent=None, can_resume=False):
        super().__init__(parent)
        self.setWindowTitle(APP_NAME)
        self.setMinimumWidth(420)
        self.mode = 'new'
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)
        lay.addWidget(row(logo_widget(76), label('BFT EDITION  /  DANMARK', 'eyebrow'), 1))
        lay.addWidget(label('Nyt spil', 'title'))
        lay.addWidget(label('Du starter i Høje på Fyn. Vælg spillets længde.', 'muted'))
        self.name = QLineEdit()
        self.name.setPlaceholderText('Spiller')
        self.name.setMaxLength(24)
        self.city = label('Høje på Fyn', 'section')
        self.duration = QComboBox()
        for n in DURATIONS:
            self.duration.addItem(f'{n} dage' + (' · 1 år' if n == 365 else ''), n)
        for title, field in [('SPILLERNAVN', self.name), ('STARTBY', self.city), ('TIDSHORISONT', self.duration)]:
            lay.addWidget(label(title, 'eyebrow'))
            lay.addWidget(field)
        lay.addWidget(label('Start: 2.000 sorte kr. · 5.500 kr. i gæld\n1,5 % daglig rente. Hver rejse koster én dag.', 'muted'))
        lay.addWidget(button('Start nyt spil', self.accept, 'primary'))
        if can_resume:
            lay.addWidget(button('Fortsæt gemt spil', self.resume))
        lay.addWidget(button('Annuller', self.reject))
        self.name.setFocus()

    def resume(self):
        self.mode = 'resume'
        self.accept()


class Window(QMainWindow):
    pages = ['Marked', 'Rejser', 'Shop', 'Bank', 'Mules', 'Investeringer', 'Highscores', 'Om spillet', 'Hændelser', 'Dit resultat']

    def __init__(self, game=None):
        super().__init__()
        self.g = game
        self.drug = 'hash'
        self.sell_drug = 'hash'
        self.last_notice = 'Vælg en vare, køb ind og rejs til et nyt marked.'
        self.panel = None
        self.panel_page = None
        self.event_dialog = None
        self._event_key = None
        self.police_open = False
        self.police_dialog = None
        self.update_police_preview = None
        self.setWindowTitle(APP_NAME)
        self.resize(880, 780)
        self.setMinimumSize(800, 720)
        self.setWindowIcon(make_icon())
        self.main = QWidget()
        self.setCentralWidget(self.main)
        self.ml = QVBoxLayout(self.main)
        self.ml.setContentsMargins(12, 10, 12, 8)
        self.ml.setSpacing(8)
        game_menu = self.menuBar().addMenu('Spil')
        game_menu.addAction('Nyt spil…', self.new)
        game_menu.addAction('Highscores…', lambda: self.go(6))
        game_menu.addSeparator()
        game_menu.addAction('Gem og luk', self.close)
        game_menu.addAction('Hændelser…', lambda: self.go(8)).setShortcut('F7')
        game_menu.addAction('Dit resultat…', lambda: self.go(9))
        for title, page, shortcut in [('Bank',3,'F3'),('Shop',2,'F4'),('Mules',4,'F5'),('Investeringer',5,'F6')]:
            game_menu.addAction(title, lambda p=page:self.go(p)).setShortcut(shortcut)
        help_menu = self.menuBar().addMenu('Hjælp')
        help_menu.addAction('Spilregler og danske data…', lambda: self.go(7))
        if game:
            self.render()

    def new(self, first=False):
        if not first and self.g and not self.g.s['finished']:
            if QMessageBox.question(self, 'Nyt spil?', 'Et nyt spil erstatter dit nuværende autosave. Fortsæt?',
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
        dialog = StartDialog(self, first and SAVE.exists())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            if first:
                self.close()
            return
        try:
            self.g = Game.load(SAVE) if dialog.mode == 'resume' else new_game(dialog.name.text(), 'Høje på Fyn', dialog.duration.currentData())
        except Exception:
            QMessageBox.warning(self, 'Gemningen kunne ikke læses', 'Den gemte fil er beskadiget eller bruger en anden version. Den er ikke ændret. Start et nyt spil for at fortsætte.')
            if first:
                self.new(True)
            return
        self.autosave()
        self.render()
        if self.panel and self.panel.isVisible():
            self.refresh_panel()
        QTimer.singleShot(0, self.present_day_events)

    def go(self, page):
        if not self.g:
            return
        if self.panel:
            self.panel.close()
        self.panel_page = page
        self.panel = QDialog(self)
        self.panel.setWindowTitle(self.pages[page])
        self.panel.setWindowModality(Qt.WindowModality.WindowModal)
        self.panel.resize(640 if page != 7 else 780, 560)
        layout = QVBoxLayout(self.panel)
        self.panel_scroll = QScrollArea()
        self.panel_scroll.setWidgetResizable(True)
        layout.addWidget(self.panel_scroll)
        layout.addWidget(button('Luk', self.panel.close))
        self.refresh_panel()
        self.panel.show()

    def refresh_panel(self):
        if not self.panel:
            return
        previous = self.panel_scroll.verticalScrollBar().value()
        body = QWidget()
        body.setObjectName('pageContent')
        self.bl = QVBoxLayout(body)
        self.bl.setContentsMargins(2, 2, 8, 2)
        self.bl.addWidget(label(f"Sorte penge: {money(self.g.s['black'])} · Lovlige: {money(self.g.s['clean'])} · Gæld: {money(self.g.s['debt'])}", 'muted'))
        [None, self.travel, self.shop, self.bank, self.mules, self.invest, self.scores, self.about, self.events, self.results][self.panel_page]()
        self.bl.addStretch()
        old = self.panel_scroll.takeWidget()
        if old:
            old.hide()
            old.deleteLater()
        self.panel_scroll.setWidget(body)
        self.panel_scroll.verticalScrollBar().setValue(previous)

    def autosave(self):
        if not self.g:
            return
        try:
            self.g.save(SAVE)
            if self.g.s['finished']:
                scores = self.read_scores(all_rulesets=True)
                entry = self.g.public_score()
                if not any(x.get('id') == entry['id'] for x in scores):
                    scores.append(entry)
                    temp = SCORES.with_suffix('.tmp')
                    temp.write_text(json.dumps(scores, ensure_ascii=False, indent=2), encoding='utf-8')
                    temp.replace(SCORES)
        except (OSError, ValueError) as e:
            self.last_notice = 'Kunne ikke gemme: ' + str(e)
            QMessageBox.warning(self, 'Spillet kunne ikke gemmes', str(e))

    def read_scores(self, all_rulesets=False):
        if not SCORES.exists():
            return []
        try:
            values = json.loads(SCORES.read_text(encoding='utf-8'))
            if not isinstance(values, list):
                raise ValueError('Ugyldig highscorefil.')
            return [s for s in values if isinstance(s, dict) and (all_rulesets or s.get('ruleset') == RULESET) and
                    isinstance(s.get('score'), int) and s.get('duration') in DURATIONS]
        except (ValueError, OSError):
            return []

    def act(self, action, **args):
        try:
            self.g.execute(action, **args)
        except (RuleError, KeyError, ValueError) as e:
            QMessageBox.information(self, 'Handlingen kunne ikke gennemføres', str(e))
            return
        self.last_notice = self.g.s['log'][0].split('  ·  ', 1)[-1]
        self.autosave()
        self.render()
        if self.panel and self.panel.isVisible():
            self.refresh_panel()
        QTimer.singleShot(0, self.present_day_events)

    def present_day_events(self):
        """Acknowledge each notice once, including a tip arriving on the same day."""
        if not self.g or not self.isVisible() or self.event_dialog or self.police_open:
            return
        key = (self.g.s['id'], self.g.s['day'])
        if key != self._event_key:
            self._event_key = key
            self._seen_notices = set()
        events = [e for e in self.g.s.get('day_events', [])
                  if json.dumps(e, sort_keys=True) not in self._seen_notices]
        if events:
            self._seen_notices.update(json.dumps(e, sort_keys=True) for e in events)
            d = QDialog(self)
            self.event_dialog = d
            d.setObjectName('dayEvents')
            d.setWindowTitle(f"Dag {self.g.s['day']} · Hændelser")
            d.setWindowModality(Qt.WindowModality.WindowModal)
            d.setFixedWidth(530)
            lay = QVBoxLayout(d)
            lay.setContentsMargins(24, 24, 24, 24)
            lay.setSpacing(16)
            lay.addWidget(label('Dagens hændelser', 'title'))
            lay.addWidget(label(f"{self.g.s['city']} · {DISTRICTS[self.g.s['city']][self.g.s['district']]}", 'muted'))
            for event in events:
                card = QFrame(); card.setObjectName('card')
                content = QVBoxLayout(card); content.setContentsMargins(16, 14, 16, 14)
                content.setSpacing(10)
                if event['kind'] == 'market':
                    icon = QLabel(); icon.setPixmap(drug_icon(event['drug']).pixmap(40, 40))
                    content.addWidget(row(icon, label(event['title'], 'section'), 1))
                    content.addWidget(label(event['text']))
                    price = label(f"{DRUGS[event['drug']][0]}  {event['change']:+d} %", 'title')
                    price.setStyleSheet('color: ' + ('#26724d' if event['change'] < 0 else '#a23f3f'))
                    content.addWidget(price)
                    content.addWidget(label(f"{money(event['before'])} → {money(event['price'])} pr. enhed", 'section'))
                    content.addWidget(label('Dagens pris gælder både køb og salg. Prisen ændres igen, når du rejser eller går til næste dag.', 'muted'))
                else:
                    content.addWidget(label(event['title'], 'section'))
                    content.addWidget(label(event['text']))
                    if event['kind']=='clear_police':content.addWidget(label('GREEN CARD  ·  50 % chance ved næste forklaring', 'profit'))
                lay.addWidget(card)
            lay.addWidget(button('Fortsæt til politikontrol' if self.g.s['police'] else 'Til markedet', d.accept, 'primary'))
            def acknowledged(_):
                self.event_dialog = None
                d.deleteLater()
                QTimer.singleShot(0, self.present_day_events)
            d.finished.connect(acknowledged)
            d.open()
            return
        if self.g.s['police']:
            self.police_open = True
            try:
                self.police()
            finally:
                self.police_open = False

    def finish(self):
        if QMessageBox.question(self, 'Afslut spillet?', 'Kun lovlig nettoformue tæller. Sorte penge, varer og ventende omdannelser tæller ikke. Afslut nu?',
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.act('finish')

    def police(self):
        if not self.g.s['police']:
            return
        d = QDialog(self)
        d.setWindowTitle('Politiet stopper dig')
        d.setMinimumWidth(510)
        lay = QVBoxLayout(d)
        lay.setContentsMargins(28, 28, 28, 28)
        lay.setSpacing(18)
        lay.addWidget(label('Et møde, du ikke planlagde.', 'title'))
        chances=label('', 'muted');chances.setObjectName('police_chances');lay.addWidget(chances)
        tip_note=label('', 'section');tip_note.setObjectName('police_tip');lay.addWidget(tip_note)
        def refresh_preview():
            # TIP-7: another player may tip us while this modal is already open.
            # Never keep displaying the old odds or act after a host-issued DNF.
            if not self.g.s['police'] or self.g.s['finished']:
                d.reject();return
            chance=round(WEAPONS[self.g.s['weapon']][2]*100)
            escape=round(self.g.run_chance*100)
            chances.setText(f'Helbred: {self.g.s["health"]} / 100\nVåben: {WEAPONS[self.g.s["weapon"]][0]}\nKampchance: {chance} % · Flugtchance: {escape} %')
            tip_note.setText('Tippet til dag '+str(self.g.s.get('tip_until_day',0))+' · Mislykket flugt giver halv skade og kan ikke dræbe dig.')
            tip_note.setVisible(self.g.tip_active)
        self.police_dialog=d;self.update_police_preview=refresh_preview;refresh_preview()
        lay.addWidget(label('Overgivelse koster alle dine varer og 25 % af dine sorte kontanter. Dine bankpenge og lovlige aktiver er sikre. Kamp og flugt kan koste helbred.'))
        if self.g.s['green_card']:
            lay.addWidget(label('Green card: Forklar dig med 50 % chance. Kortet bruges op. Ved afslag mister du varer og 25 % af sorte kontanter; ingen helbredsskade.'))
        choice = ['surrender']
        def pick(value):
            choice[0] = value
            d.accept()
        lay.addWidget(row(button('Kæmp', lambda: pick('fight'), 'danger'),
                          button('Flygt', lambda: pick('run'), 'primary'),
                          button('Overgiv dig', lambda: pick('surrender'))))
        if self.g.s['green_card']:
            lay.addWidget(button('Brug green card · forklar dig (50 %)', lambda: pick('explain'), 'primary'))
        lay.addWidget(label('Lukker du dette vindue, overgiver du dig.', 'muted'))
        try:d.exec()
        finally:
            self.police_dialog=None;self.update_police_preview=None;d.deleteLater()
        if self.g.s['police'] and not self.g.s['finished']:self.act('police', choice=choice[0])

    def render(self):
        if self.update_police_preview:self.update_police_preview()
        while self.ml.count():
            item = self.ml.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        s = self.g.s
        brand = QFrame();brand.setObjectName('brand');brandline = QHBoxLayout(brand)
        brandline.setContentsMargins(8, 0, 8, 0)
        brandline.addWidget(label('DOPE WARS  /  BFT EDITION', 'eyebrow', False));brandline.addStretch()
        brandline.addWidget(label(f"{s['name']}  ·  Dag {s['day']} / {s['duration']}", wrap=False))
        self.ml.addWidget(brand)
        active = not s['finished'] and not s['police']
        self.setWindowTitle(f"{APP_NAME} — Dag {s['day']} af {s['duration']}")
        top = QWidget()
        grid = QGridLayout(top)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        stats = QWidget()
        sl = QGridLayout(stats)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setVerticalSpacing(4)
        for i, (title, value, color) in enumerate([
            ('Kontanter', money(s['black']), '#70de9d'),
            ('Bank', money(s['clean']), '#70de9d'),
            ('Gæld', money(s['debt']), '#ff8585'),
            ('Våben', WEAPONS[s['weapon']][0], '#ead879')]):
            line = label(title + '   ' + value, wrap=False)
            line.setStyleSheet(f'background: #182127; color: {color}; font-size: 17px; font-weight: 600; padding: 6px 9px; border-radius: 3px;')
            if i == 3 and s['weapon']:
                strip = row(weapon_icon(s['weapon'], '#ead879'), line, 1)
                strip.setStyleSheet('background: #182127; border-radius: 3px;')
                sl.addWidget(strip, i, 0)
            else:
                sl.addWidget(line, i, 0)
        grid.addWidget(stats, 0, 0)
        travel = QWidget()
        tr = QVBoxLayout(travel)
        tr.setContentsMargins(0, 0, 0, 0)
        tr.setSpacing(6)
        tr.addWidget(label(f"Rejs fra {s['city']} · {DISTRICTS[s['city']][s['district']]}", 'section'))
        buttons = QGridLayout()
        cities = [c for c in CITIES if c != s['city']]
        for i, city in enumerate(cities):
            b = button(city, lambda c=city: self.act('travel', city=c, district=0))
            b.setEnabled(active and s['day'] < s['duration'])
            buttons.addWidget(b, i//3, i%3)
        tr.addLayout(buttons)
        local = button('Områder i byen…', lambda: self.go(1))
        tr.addWidget(row(label('En rejse = én dag', 'muted'), 1, local))
        grid.addWidget(travel, 0, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self.ml.addWidget(top)
        health = QProgressBar()
        health.setRange(0, 100)
        health.setValue(s['health'])
        health.setFormat('Helbred %p%')
        self.ml.addWidget(row(health, button('Bank', lambda: self.go(3)), button('Shop', lambda: self.go(2)),
                              button('Mules', lambda: self.go(4)), button('Investeringer', lambda: self.go(5))))
        lists = QWidget()
        ll = QHBoxLayout(lists)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(12)
        self.market_keys = list(DRUGS)
        self.stock_keys = [k for k in DRUGS if s['inventory'][k]]
        self.market_table = table(['Vare', 'Dagens pris'], [[DRUGS[k][0], money(self.g.quote(k))] for k in self.market_keys])
        self.market_table.horizontalHeaderItem(1).setToolTip('Samme pris ved køb og salg. Ingen handelsfradrag.')
        self.stock_table = table(['Vare', 'Antal', 'Gns. købspris'], [[DRUGS[k][0], s['inventory'][k], average_cost(s['cost'][k], s['inventory'][k])] for k in self.stock_keys])
        self.stock_table.horizontalHeaderItem(2).setToolTip('Vægtet gennemsnit af det, du har betalt pr. enhed. Du sælger til dagens pris i markedet, uden handelsfradrag.')
        for i, k in enumerate(self.stock_keys):
            self.stock_table.item(i, 2).setToolTip('Dagens salgspris: ' + money(self.g.sell_quote(k)) + ' pr. enhed')
        for title, t in [('Marked · ' + DISTRICTS[s['city']][s['district']], self.market_table), (f'Taske · {self.g.used} / {self.g.capacity} enheder', self.stock_table)]:
            pane = QWidget()
            pl = QVBoxLayout(pane)
            pl.setContentsMargins(0, 0, 0, 0)
            pl.setSpacing(5)
            pl.addWidget(label(title, 'section'))
            t.setAlternatingRowColors(True)
            pl.addWidget(t, 1)
            ll.addWidget(pane, 1)
        for t, keys in [(self.market_table,self.market_keys),(self.stock_table,self.stock_keys)]:
            t.setIconSize(QSize(26,26));t.verticalHeader().setDefaultSectionSize(32)
            for i,key in enumerate(keys):t.item(i,0).setIcon(drug_icon(key))
            t.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
            for col in range(1,t.columnCount()):t.horizontalHeader().setSectionResizeMode(col,QHeaderView.ResizeMode.ResizeToContents)
        self.ml.addWidget(lists, 1)
        self.buy_total = label('', 'muted'); self.sell_total = label('', 'muted')
        self.buy_qty = spin(self.g.capacity)
        self.sell_qty = spin(self.g.capacity)
        self.buy_btn = button('Køb', lambda: self.act('buy', drug=self.drug, qty=self.buy_qty.value()), 'primary')
        self.sell_btn = button('Sælg', lambda: self.act('sell', drug=self.sell_drug, qty=self.sell_qty.value()), 'primary')
        def update():
            mr = self.market_table.currentRow()
            sr = self.stock_table.currentRow()
            if mr >= 0:
                self.drug = self.market_keys[mr]
            if sr >= 0:
                self.sell_drug = self.stock_keys[sr]
            affordable = min(self.g.capacity-self.g.used, s['black']//self.g.quote(self.drug))
            owned = s['inventory'][self.sell_drug] if sr >= 0 else 0
            self.buy_qty.setRange(1 if affordable else 0, affordable)
            self.sell_qty.setRange(1 if owned else 0, owned)
            self.buy_qty.setEnabled(active and affordable>0);self.sell_qty.setEnabled(active and owned>0)
            self.buy_btn.setEnabled(active and mr >= 0 and affordable > 0)
            self.sell_btn.setEnabled(active and owned > 0)
            self.sell_btn.setToolTip('Sælg til ' + money(self.g.sell_quote(self.sell_drug)) + ' pr. enhed. Samme pris som ved køb.')
        def totals():
            self.buy_total.setText('Køb i alt: ' + money(self.buy_qty.value()*self.g.quote(self.drug)))
            qty=self.sell_qty.value();price=self.g.sell_quote(self.sell_drug)
            owned=s['inventory'][self.sell_drug]
            cost=s['cost'][self.sell_drug]*qty//owned if owned else 0
            profit=price*qty-cost
            self.sell_total.setText(f'Salg: {money(price*qty)}  ·  '+('gevinst ' if profit>=0 else 'tab ')+money(abs(profit)))
            self.sell_total.setStyleSheet('color: '+('#26724d' if profit>=0 else '#a23f3f'))
            self.sell_total.setToolTip('Dagens købs- og salgspris: '+money(price)+' pr. enhed. Ingen handelsfradrag. Gevinst/tab sammenlignes med dit gennemsnitlige indkøb.')
        self.buy_qty.valueChanged.connect(totals);self.sell_qty.valueChanged.connect(totals)
        self.market_table.itemSelectionChanged.connect(update)
        self.market_table.itemSelectionChanged.connect(totals)
        self.stock_table.itemSelectionChanged.connect(update)
        self.stock_table.itemSelectionChanged.connect(totals)
        self.market_table.selectRow(self.market_keys.index(self.drug))
        if self.stock_keys:
            self.stock_table.selectRow(self.stock_keys.index(self.sell_drug) if self.sell_drug in self.stock_keys else 0)
        update();totals()
        buymax = button('Maks.', lambda: self.buy_qty.setValue(self.buy_qty.maximum()))
        sellmax = button('Alle', lambda: self.sell_qty.setValue(self.sell_qty.maximum()))
        buymax.setEnabled(self.buy_btn.isEnabled());sellmax.setEnabled(self.sell_btn.isEnabled())
        self.market_table.itemSelectionChanged.connect(lambda:buymax.setEnabled(self.buy_btn.isEnabled()))
        self.stock_table.itemSelectionChanged.connect(lambda:sellmax.setEnabled(self.sell_btn.isEnabled()))
        controls = QWidget()
        cl = QHBoxLayout(controls)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(12)
        cl.addWidget(row(label('Antal'), self.buy_qty, buymax, self.buy_btn), 1)
        cl.addWidget(row(label('Antal'), self.sell_qty, sellmax, self.sell_btn), 1)
        self.ml.addWidget(controls)
        totalsrow=QWidget();trl=QHBoxLayout(totalsrow);trl.setContentsMargins(0,0,0,0)
        trl.addWidget(self.buy_total,1);trl.addWidget(self.sell_total,1);self.ml.addWidget(totalsrow)
        market_note=label(s['market_event'] or 'Samme pris ved køb og salg. Rejs eller vent for nye priser.', 'section' if s['market_event'] else 'muted')
        market_note.setWordWrap(False)
        detail=s.get('market_event_detail')
        market_note.setToolTip(detail['text'] if detail else 'Prisprofiler og markedsbegivenheder er fiktive spilregler.')
        card_note=label('Green card: klar · 50 %' if s['green_card'] else 'Green card: —','profit' if s['green_card'] else 'muted',False)
        self.ml.addWidget(row(market_note,1,card_note))
        risk_note=('Næste dags kontrol: '+str(round(self.g.police_risk(next_day=True)*100))+' %') if s['day']<s['duration'] else 'Sidste spildag'
        risk_note+=' · Heat '+str(s['heat'])+'/100'
        if self.g.tip_active:risk_note+=' · Tippet til dag '+str(s['tip_until_day'])
        if not s['finished']:
            risk=label(risk_note,'muted');risk.setObjectName('police_risk');self.ml.addWidget(risk)
        score = label('Offentlig score: ' + money(self.g.score), 'section', False)
        score.setToolTip('Lovlige penge + aktivernes salgsværdi − gæld. Sorte penge tæller ikke.')
        nextday = button('Afslut spillet' if s['day'] == s['duration'] else 'Næste dag',
                         self.finish if s['day'] == s['duration'] else lambda: self.act('wait'))
        nextday.setEnabled(active)
        self.ml.addWidget(row(score, 1, button('Hændelser', lambda:self.go(8)), button('Highscores', lambda: self.go(6)), button('Resultat',lambda:self.go(9)) if s['finished'] else nextday))
        note = label(('Spillet er slut · ' + s['reason']) if s['finished'] else self.last_notice)
        note.setObjectName('notice')
        note.setMaximumHeight(44)
        note.setToolTip(self.last_notice)
        self.ml.addWidget(note)

    def active_button(self, text, action, role=None, **args):
        b = button(text, lambda: self.act(action, **args), role)
        enabled=not self.g.s['finished'] and not self.g.s['police']
        if action=='heal':enabled=enabled and self.g.s['health']<100 and self.g.s['black']>=(100-self.g.s['health'])*20
        if action=='asset':enabled=enabled and len(self.g.s['assets'])<6 and self.g.s['clean']>=ASSETS[args['tier']][1]
        if action=='sell_asset':enabled=enabled and not self.g.asset(args['aid'])['queue']
        if action=='dismiss':enabled=enabled and not sum(self.g.mule(args['mid'])['inventory'].values())
        b.setEnabled(enabled)
        return b

    def travel(self):
        self.bl.addWidget(label('Vælg et område i din nuværende by. Rejsen tager én dag.', 'muted'))
        for i, district in enumerate(DISTRICTS[self.g.s['city']]):
            b = self.active_button(district + '  ·  ' + area_description(self.g.s['city'], i), 'travel', city=self.g.s['city'], district=i)
            b.setEnabled(not self.g.s['finished'] and self.g.s['day'] < self.g.s['duration'] and i != self.g.s['district'])
            self.bl.addWidget(b)
        self.bl.addWidget(label('Byområderne bruger virkelige stednavne; Højes seks zoner er fiktive. Prisprofilerne er fiktiv spilbalance, ikke lokal statistik. Dagens udsving kan opveje rabatten.', 'muted'))

    def shop(self):
        self.bl.addWidget(label('Udstyr betales med sorte kontanter. Opgraderinger erstatter dit gamle udstyr og kan ikke sælges tilbage.', 'muted'))
        bags, bl = card('Mere plads. Flere muligheder.', 'Tasker · permanent kapacitet')
        for i, (name, capacity, price) in enumerate(BAGS):
            if i == 0:
                continue
            b = self.active_button('Køb · ' + money(price), 'bag', tier=i)
            b.setEnabled(not self.g.s['finished'] and i > self.g.s['bag'] and self.g.s['black']>=price)
            if i==self.g.s['bag']:b.setText('Udstyret')
            bl.addWidget(row(label(f'{name}\n{capacity} enheder', 'section'), 1, b))
        self.bl.addWidget(bags)
        weapons, wl = card('Når politiet kommer', 'Våben forbedrer kampchancen. Du kan stadig blive såret eller dø.')
        for i, (name, price, chance) in enumerate(WEAPONS):
            if i == 0:
                continue
            b = self.active_button('Køb · ' + money(price), 'weapon', tier=i)
            b.setEnabled(not self.g.s['finished'] and i > self.g.s['weapon'] and self.g.s['black']>=price)
            if i==self.g.s['weapon']:b.setText('Udstyret')
            wl.addWidget(row(weapon_icon(i), label(f'{name}\n{round(chance*100)} % chance i kamp'), 1, b))
        self.bl.addWidget(weapons)
        c, l = card('Tilbage på benene', f'Helbred: {self.g.s["health"]} / 100 · 20 kr. pr. manglende point')
        l.addWidget(self.active_button('Genopret helbred · ' + money((100-self.g.s['health'])*20), 'heal'))
        self.bl.addWidget(c)

    def maximum_control(self, field, submit, limit, *signals):
        """Keep each amount and its action in sync with the available balance/capacity."""
        maximum = button('Maks.', lambda: field.setValue(field.maximum()))
        maximum.setToolTip('Udfyld det største mulige beløb eller antal. Handlingen gennemføres først på handlingsknappen.')
        def update(*_):
            available = max(0, min(10**12 if isinstance(field,MoneySpinBox) else 2_000_000_000, int(limit())))
            field.setRange(1 if available else 0, available)
            enabled = available > 0 and not self.g.s['finished'] and not self.g.s['police']
            field.setEnabled(enabled)
            maximum.setEnabled(enabled)
            submit.setEnabled(enabled)
        for signal in signals:
            signal.connect(update)
        update()
        return maximum

    def bank(self):
        c, l = card('Kredit har en pris.', '1,5 % rente hver dag. Renten lægges til gælden, også mens du venter.')
        l.addWidget(label('Du kan låne yderligere ' + money(self.g.loan_room), 'metric'))
        l.addWidget(label('Rammen er 10.000 kr. plus 40 % af aktivernes salgsværdi, fratrukket eksisterende gæld. Lån udbetales som sorte kontanter og øger gælden.', 'muted'))
        amount = MoneySpinBox(value=1000);amount.setObjectName('bank_amount')
        kind = QComboBox()
        for name, value in [('Optag lån → kontanter', 'borrow'), ('Afdrag med sorte kontanter', 'repay_black'),
                            ('Afdrag med lovlige penge', 'repay_clean'),
                            ('Flyt lovlige penge til sort økonomi', 'to_black')]:
            kind.addItem(name, value)
        kind.setObjectName('bank_kind')
        submit = button('Gennemfør', lambda q=amount,k=kind: self.act('bank', kind=k.currentData(), amount=q.value()), 'primary')
        submit.setEnabled(not self.g.s['finished'])
        def bank_limit(k=kind):
            s = self.g.s
            return {'borrow': self.g.loan_room, 'repay_black': min(s['black'],s['debt']),
                    'repay_clean': min(s['clean'],s['debt']), 'to_black': s['clean']}[k.currentData()]
        maximum = self.maximum_control(amount, submit, bank_limit, kind.currentIndexChanged)
        l.addWidget(kind)
        l.addWidget(row(amount, maximum, submit))
        self.bl.addWidget(c)
        c, l = card('Hvidvask kontanter', 'Fiktiv spilmekanik. Højere gebyr giver kortere ventetid. Den præcise udbetalingsdag er skjult og fastlægges ved bestilling.')
        amount = MoneySpinBox(value=1000);amount.setObjectName('wash_amount')
        tier = QComboBox()
        for i, (name, fee, low, high) in enumerate(WASH_OPTIONS):
            tier.addItem(f'{name} · {fee} % gebyr · {low}–{high} dage', i)
        tier.setObjectName('wash_tier')
        preview = label('', 'muted')
        def update_wash():
            _, fee, low, high = WASH_OPTIONS[tier.currentData()]
            preview.setText(f'Til banken efter gebyr: {money(amount.value()*(100-fee)//100)}. Ventetid: {low}–{high} dage.')
        amount.valueChanged.connect(update_wash)
        tier.currentIndexChanged.connect(update_wash)
        update_wash()
        submit = button('Start hvidvaskning', lambda: self.act('wash', amount=amount.value(), tier=tier.currentData()), 'primary')
        submit.setEnabled(not self.g.s['finished'])
        maximum = self.maximum_control(amount, submit, lambda: self.g.s['black'] if self.g.s['black']>=2 else 0)
        l.addWidget(tier)
        l.addWidget(row(amount, maximum, submit))
        l.addWidget(preview)
        update_wash()
        l.addWidget(label('Ventende beløb tæller ikke i scoren. Slutter spillet før udbetalingen, får du ikke beløbet med. En bestilling kan ikke annulleres.', 'muted'))
        for o in self.g.s['washing']:
            name, fee, low, high = WASH_OPTIONS[o['tier']]
            elapsed = self.g.s['day']-o['started']
            l.addWidget(label(f"{name}: {money(o['payout'])} til banken · ventet {elapsed} dage · forventet dag {o['started']+low}–{o['started']+high}"))
        self.bl.addWidget(c)
        c, l = card('To økonomier. Én slutscore.')
        l.addWidget(label('Sorte kontanter bruges til varer, udstyr og mules. Lån udbetales som kontanter. Kontanter kan ikke indsættes direkte i banken.'))
        l.addWidget(label('Banken rummer lovlige likvider til investeringer og afdrag. Hæv til kontanter for at bruge dem på varer. Flytter du dem til den sorte økonomi, falder din offentlige score. De kan blive lovlige igen via hvidvaskning eller virksomhederne.'))
        l.addWidget(label('Score = lovlige penge + aktivernes salgsværdi − hele gælden.', 'section'))
        self.bl.addWidget(c)

    def mules(self):
        c, l = card('Et netværk uden for din egen by', 'Du sender varer; dine mules sælger automatisk ved dagens skifte. Højst seks ansatte.')
        city, tier = QComboBox(), QComboBox()
        city.addItems([x for x in CITIES if x != self.g.s['city']])
        for i, (name, cost, volume, cut) in enumerate(MULE_TIERS):
            tier.addItem(f'{name} · {volume}/dag · {cut} % cut · {money(cost)}', i)
        l.addWidget(city)
        l.addWidget(tier)
        hire = button('Hyr mule', lambda: self.act('hire', city=city.currentText(), tier=tier.currentData()), 'primary')
        def can_hire():
            hire.setEnabled(not self.g.s['finished'] and len(self.g.s['mules'])<6 and self.g.s['black']>=MULE_TIERS[tier.currentData()][1])
        tier.currentIndexChanged.connect(can_hire);can_hire()
        l.addWidget(hire)
        l.addWidget(label('Større lager giver større risiko for tilbagefald: 0,1 % + 0,005 procentpoint pr. enhed, højst 2,6 % pr. aktiv dag. Et tilbagefald koster 25 % af lageret (oprundet) og to dages pause.', 'muted'))
        self.bl.addWidget(c)
        if not self.g.s['mules']:
            self.bl.addWidget(label('Dit netværk starter med din første ansættelse.', 'muted'))
        for m in self.g.s['mules']:
            name, _, volume, cut = MULE_TIERS[m['tier']]
            c, l = card(f'{m["city"]} · {name}', f'{volume} enheder/dag · {cut} % af omsætningen · indtjent efter cut: {money(m["earned"])}')
            stock = '  ·  '.join(f'{DRUGS[k][0]} {v}' for k,v in m['inventory'].items() if v) or 'Intet på lager'
            l.addWidget(label(stock))
            units=sum(m['inventory'].values())
            l.addWidget(label(('Risiko ved næste salg: '+f'{mule_risk(units)*100:.2f}'.replace('.',',')+' %') if units else 'Intet lager · ingen risiko for tilbagefald', 'muted'))
            if m['cooldown']:
                l.addWidget(label(f'Pause: {m["cooldown"]} dage tilbage', 'muted'))
            drug, qty = QComboBox(), spin(500)
            for k,(n,_) in DRUGS.items():
                drug.addItem(f'{n} · du har {self.g.s["inventory"][k]}', k)
            send = button('Send varer', lambda mid=m['id'], d=drug,q=qty: self.act('dispatch', mid=mid, drug=d.currentData(), qty=q.value()), 'primary')
            send.setEnabled(not self.g.s['finished'])
            maximum = self.maximum_control(qty, send,
                lambda d=drug,m=m: min(self.g.s['inventory'][d.currentData()], 500-sum(m['inventory'].values())),
                drug.currentIndexChanged)
            l.addWidget(drug)
            l.addWidget(row(qty, maximum, send))
            l.addWidget(self.active_button('Afskedig (kræver tomt lager)', 'dismiss', mid=m['id']))
            self.bl.addWidget(c)

    def invest(self):
        self.bl.addWidget(label('Køb med lovlige penge. Placér sorte penge i virksomhedens kø, og modtag lovlige penge efter ventetid og gebyr. En fiktiv spilmekanik.', 'muted'))
        c, l = card('Byg din lovlige portefølje')
        for i, (name, cost, cap, fee, delay, income) in enumerate(ASSETS):
            l.addWidget(row(label(f'{name}\n{money(cap)}/dag · {fee} % gebyr · {delay} dages ventetid\nLovligt afkast: {money(income)}/dag · salgsværdi: {money(cost*60//100)}'),
                            1, self.active_button('Køb · ' + money(cost), 'asset', tier=i)))
        self.bl.addWidget(c)
        for a in self.g.s['assets']:
            name, cost, cap, fee, delay, income = ASSETS[a['tier']]
            pending = sum(o['remaining'] for o in a['queue'])
            c, l = card(name, f'I kø: {money(pending)} / {money(cap*10)} · omdannet: {money(a["converted"])} · afkast: {money(a["income"])}')
            if a['queue']:
                next_ready = min(o['ready'] for o in a['queue'])
                l.addWidget(label(f'Næste behandling: dag {max(self.g.s["day"]+1,next_ready)}. Maks. {money(cap)} samlet pr. dag.', 'muted'))
            amount = MoneySpinBox(value=500)
            send = button('Sæt sorte penge i kø', lambda aid=a['id'],q=amount: self.act('fund', aid=aid, amount=q.value()), 'primary')
            send.setEnabled(not self.g.s['finished'])
            maximum = self.maximum_control(amount, send,
                lambda a=a,cap=cap: min(self.g.s['black'], cap*10-sum(o['remaining'] for o in a['queue'])))
            l.addWidget(row(amount, maximum, send))
            l.addWidget(self.active_button('Sælg aktiv · ' + money(cost*60//100), 'sell_asset', aid=a['id']))
            self.bl.addWidget(c)

    def scores(self):
        c, l = card('Den formue, der kan ses', 'Separate lokale lister for hver tidshorisont. Kun afsluttede spil registreres.')
        duration = QComboBox()
        for n in DURATIONS:
            duration.addItem(f'{n} dage', n)
        duration.setCurrentIndex(DURATIONS.index(self.g.s['duration']))
        rules = QComboBox();rules.setObjectName('score_ruleset')
        rules.addItem('Nuværende regler · ' + VERSION, RULESET)
        all_scores = self.read_scores(all_rulesets=True)
        for old_rule in sorted({x['ruleset'] for x in all_scores if isinstance(x.get('ruleset'), str) and x['ruleset'] != RULESET}, reverse=True):
            rules.addItem('Tidligere regler · ' + old_rule, old_rule)
        t = table(['#', 'SPILLER', 'SCORE', 'SLUTDAG'], [], 360)
        def update():
            scores = sorted([x for x in all_scores if x['duration'] == duration.currentData() and x.get('ruleset') == rules.currentData()], key=lambda x:x['score'], reverse=True)[:20]
            t.setRowCount(len(scores))
            for i,s in enumerate(scores):
                for j,value in enumerate([i+1,s.get('name','Spiller'),money(s['score']),s.get('day','—')]):
                    t.setItem(i,j,QTableWidgetItem(str(value)))
        duration.currentIndexChanged.connect(update)
        rules.currentIndexChanged.connect(update)
        update()
        l.addWidget(row(duration, rules))
        l.addWidget(t)
        l.addWidget(label('Sorte kontanter, varer og ventende omdannelser tæller ikke. Dette er din lokale singleplayer-liste; LAN har sin egen fælles stilling.', 'muted'))
        if not self.g.s['finished']:
            l.addWidget(button('Afslut og registrér min score', self.finish, 'primary'))
        self.bl.addWidget(c)

    def about(self):
        self.bl.addWidget(logo_widget(96))
        c, l = card('BFT edition', 'Et nyt, selvstændigt Windows-spil inspireret af den klassiske Dope Wars.')
        l.addWidget(label('Sådan starter du', 'section'))
        l.addWidget(label('Køb varer, rejs til et nyt marked, og sælg dyrere. Afdrag gælden tidligt. Køb større tasker, beskyt dig med våben, og send varer til mules i andre byer.'))
        l.addWidget(label('Lån giver kontanter. Hvidvask dem i banken, før du køber dit første lovlige aktiv. Virksomhederne kan omdanne sorte penge over tid. Slutscoren omfatter kun lovlige penge og aktivernes salgsværdi minus gæld.'))
        l.addWidget(label('Hvert klik på Næste dag eller Rejs afregner renter, mules og investeringer. På sidste dag kan du stadig handle; afslut derefter. Død afslutter også spillet.'))
        l.addWidget(label('Køb og salg har samme dagspris uden handelsfradrag. Tasken viser dit gennemsnitlige indkøb. Store leveringer og lagerudsalg kan sænke prisen med 70–80 %. Razziaer og panikkøb kan hæve den til 3–4 gange dagens normale pris.'))
        l.addWidget(label('Prisbegivenheder har 35 % chance pr. dag og opstår senest efter fire dagsskift. Politiets grundchance er 18 % og stiger med opmærksomheden; der går højst seks dagsskift mellem kontroller. En tom taske giver et green card. Begivenheder vises automatisk.'))
        self.bl.addWidget(c)
        c, l = card('Danske data · tydeligt adskilt fra fiktion')
        l.addWidget(label('Grundlag: AU/SST, tabel 3, ugeprøver fra 2024, udgivet juni 2025. Enhed: mg pr. 1.000 personer pr. døgn. Målinger dækker renseanlæggenes oplande.'))
        l.addWidget(label('Vi sammenligner samme stof mellem byer, ikke rå mg mellem forskellige stoffer. Det er ikke antal brugere eller en rangliste over mest populære stoffer. THC-målingen skelner ikke hash fra andre cannabisprodukter; amfetamin kan også stamme fra medicin.'))
        rows = [[city] + [str(OBSERVED[k][i]).replace('.',',') for k in DRUGS] for i,city in enumerate(CITIES[:6])]
        l.addWidget(table(['OPLAND', 'THC*', 'KOKAIN*', 'AMF.', 'MDMA', 'KETAMIN', 'METAMF.'], rows, 335))
        l.addWidget(label('* THC-COOH og benzoylecgonin. Randers og Høje på Fyn har neutral profil: ingen verificeret lokal måling i dette datasæt.'))
        l.addWidget(label('Byernes prisfaktor er en forsigtig spildesign-omregning af samme-stof-forholdet til gennemsnittet, begrænset til 0,80–1,25. Stednavnene er virkelige; områdeprofiler, priser, kapaciteter, hændelser og fortjenester er fiktive.'))
        l.addWidget(label('Nyere 2025-målinger er offentliggjort i 2026. Den fulde rapport kunne ikke verificeres under denne implementering; derfor bruger denne version eksplicit 2024-tallene.'))
        l.addWidget(row(button('Åbn datakilden', lambda: QDesktopServices.openUrl(QUrl(SOURCE))),
                        button('Nyeste overvågning', lambda: QDesktopServices.openUrl(QUrl(LATEST_SOURCE)))))
        self.bl.addWidget(c)
        c, l = card('Gemning og version')
        l.addWidget(label('Automatisk gemning: ' + str(SAVE)))
        l.addWidget(label('Version ' + VERSION + ' · ruleset ' + RULESET + '\nSelvstændig gengivelse; originalens EXE er ikke ændret. Singleplayer og LAN bruger samme spilregler. LAN har automatisk søgning, eget dagtempo og værtsvalideret økonomi.'))
        self.bl.addWidget(c)

    def events(self):
        self.bl.addWidget(label('Hændelser og dagens regnskab','section'))
        self.bl.addWidget(label(self.g.s['last_summary'],'muted'))
        for entry in self.g.s['log'][:30]:self.bl.addWidget(label(entry))

    def results(self):
        s=self.g.s
        self.bl.addWidget(label('Dit slutresultat' if s['finished'] else 'Din formue lige nu','title'))
        if s['finished']:self.bl.addWidget(label(s['reason']))
        self.bl.addWidget(table(['Med i scoren','Beløb'],[
            ['Bank',money(s['clean'])],['Aktivernes salgsværdi',money(self.g.asset_value)],
            ['Gæld','−'+money(s['debt'])],['Lovlig nettoformue',money(self.g.score)]],168))
        pending=sum(o['payout'] for o in s['washing'])+sum(o['payout']-o['paid'] for a in s['assets'] for o in a['queue'])
        self.bl.addWidget(label(f'Ikke med: {money(s["black"])} i kontanter, {self.g.used} varer og {money(pending)} i ventende udbetalinger.','muted'))
        self.bl.addWidget(button('Se highscorelisten',lambda:self.go(6),'primary'))

    def closeEvent(self, event):
        self.autosave()
        event.accept()


def logo_widget(size):
    w = QLabel()
    pixmap = QPixmap(str(Path(__file__).with_name('logo.png')))
    w.setPixmap(pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
    w.setFixedSize(size, size)
    w.setToolTip('Produktgruppens valgte logo')
    return w


def weapon_icon(tier, color='#24588c'):
    """Small vector silhouettes, rendered at 2x for sharp Windows scaling."""
    pm = QPixmap(112, 64)
    pm.fill(Qt.GlobalColor.transparent)
    pm.setDevicePixelRatio(2)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    shapes = {
        1: [(8,8),(44,8),(44,15),(28,15),(23,29),(13,29),(17,17),(8,17)],
        2: [(3,23),(13,16),(26,16),(26,10),(51,10),(51,14),(30,14),(30,20),(18,20),(13,28),(3,28)],
        3: [(3,20),(13,15),(25,15),(25,11),(39,11),(39,14),(53,14),(53,17),(35,17),(32,23),(26,23),(25,19),(18,19),(13,27),(3,27)],
    }
    p.drawPolygon(QPolygonF([QPointF(x,y) for x,y in shapes[tier]]))
    if tier == 3:
        p.drawRoundedRect(25, 5, 15, 4, 1, 1)
        p.drawRect(29, 8, 3, 4)
    p.end()
    w = QLabel()
    w.setPixmap(pm)
    w.setFixedSize(56, 32)
    w.setToolTip(WEAPONS[tier][0])
    w.setAccessibleName(WEAPONS[tier][0] + ' ikon')
    return w


def make_icon():
    pm = QPixmap(128,128)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor('#163e78'))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(4,4,120,120,28,28)
    p.setPen(QColor('white'))
    font = QFont()
    font.setFamilies(['Segoe UI', 'Noto Sans', 'DejaVu Sans', 'Liberation Sans'])
    font.setPointSize(32)
    font.setWeight(QFont.Weight.Bold)
    p.setFont(font)
    p.drawText(pm.rect(),Qt.AlignmentFlag.AlignCenter,'BFT')
    p.end()
    return QIcon(pm)


def main():
    app = QApplication(sys.argv)
    load_fonts()
    app.setApplicationName(APP_NAME)
    app.setOrganizationName('BFT')
    app.setWindowIcon(make_icon())
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    from lan_ui import choose_mode, Lobby
    mode = choose_mode()
    if mode is None:return
    if mode == 'lan':
        w = Lobby(); w.show()
    else:
        w = Window(); w.show()
        QTimer.singleShot(0, lambda: w.new(True))
    sys.exit(app.exec())


def load_fonts():
    # Also supports headless Qt image rendering on Windows.
    if sys.platform != 'win32':
        return  # Linux uses installed system fonts via the fallback list in STYLE.
    fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    for name in ('segoeui.ttf', 'segoeuib.ttf', 'seguisb.ttf'):
        path = fonts / name
        if path.exists():
            QFontDatabase.addApplicationFont(str(path))


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--release-self-test':
        from release_acceptance import run
        run(Path(sys.argv[2]))
    elif len(sys.argv) == 3 and sys.argv[1] == '--lan-self-test':
        from lan_acceptance import run
        run(Path(sys.argv[2]))
    elif len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        from smoke_test import run
        run(Path(sys.argv[2]))
    else:
        main()
