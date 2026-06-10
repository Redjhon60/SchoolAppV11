"""
dashboard.py — SGS v4  (modern SaaS rebuild)

KPIs (4 per group, colour-coded):
  Students  → sky blue    : Total | Paid this month | Unpaid | Outstanding debt
  Employees → soft purple : Total employees
  Insurance → amber/orange: Total insurance (school year, Nov–Jun)
  Profit    → emerald     : Current month profit

Charts (3 new + 1 annual):
  1. Paid Students per Month          (bar – school months)
  2. Paid Expenses per Month          (bar – school months)
  3. Students Registered per Month    (line – school months)
  4. Annual Profit Evolution          (Jan–Dec full year, AnnualProfitChart)
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QGridLayout, QScrollArea, QSizePolicy, QPushButton, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PySide6.QtGui import QColor, QFont
from datetime import datetime

try:
    import matplotlib, matplotlib.ticker
    matplotlib.use('Agg')
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    HAS_MPL = True
except Exception:
    HAS_MPL = False

from models.database import (
    Student, Payment, MonthRecord, Employee, Salary,
    Setting, ExpenseCategory, ExpensePayment, SCHOOL_MONTHS
)
from themes.style import (
    BG_CARD, BORDER, TEXT_MAIN, TEXT_SUB, CLASSES
)

# ── Palette ────────────────────────────────────────────────────────────────────
# Students  — sky blue
C_STUD     = '#0EA5E9'
C_STUD_BG  = '#F0F9FF'
C_STUD_BD  = '#BAE6FD'
# Employees — soft purple
C_EMP      = '#8B5CF6'
C_EMP_BG   = '#F5F3FF'
C_EMP_BD   = '#DDD6FE'
# Insurance — amber/orange
C_INS      = '#F59E0B'
C_INS_BG   = '#FFFBEB'
C_INS_BD   = '#FDE68A'
# Profit    — emerald
C_PROF     = '#10B981'
C_PROF_BG  = '#ECFDF5'
C_PROF_BD  = '#A7F3D0'
# Loss      — red
C_LOSS     = '#EF4444'
C_LOSS_BG  = '#FEF2F2'
C_LOSS_BD  = '#FECACA'
# Revenue   — violet
C_REV      = '#6366F1'
C_REV_BG   = '#EEF2FF'
# Expenses  — rose
C_EXP      = '#F43F5E'
C_EXP_BG   = '#FFF1F2'
# Charts
C_CHART_BG = '#FAFAFA'
C_GRID     = '#F1F5F9'

_SCHOOL_CAL = {
    'Septembre':9,'Octobre':10,'Novembre':11,'Décembre':12,
    'Janvier':1,'Février':2,'Mars':3,'Avril':4,'Mai':5,'Juin':6,
}
_CAL_TO_SIDX = {9:0,10:1,11:2,12:3,1:4,2:5,3:6,4:7,5:8,6:9}
_SHORT  = ['Sep','Oct','Nov','Déc','Jan','Fév','Mar','Avr','Mai','Jun']
_SHORT_CAL = ['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc']


def _cur_school_month():
    idx = _CAL_TO_SIDX.get(datetime.now().month)
    return SCHOOL_MONTHS[idx] if idx is not None else None


def _fmt(v: float) -> str:
    if abs(v) >= 1_000_000: return f'{v/1_000_000:.2f}M'
    if abs(v) >= 1_000:     return f'{v/1_000:.1f}k'
    return f'{v:.0f}'


def _fmt_mad(v: float) -> str:
    return _fmt(v) + ' MAD'


def _shadow(widget, blur=12, offset_y=3, opacity=0.08):
    eff = QGraphicsDropShadowEffect()
    eff.setBlurRadius(blur)
    eff.setOffset(0, offset_y)
    eff.setColor(QColor(0, 0, 0, int(255 * opacity)))
    widget.setGraphicsEffect(eff)
    return widget


# ── Animated KPI card ─────────────────────────────────────────────────────────

class KpiCard(QFrame):
    """
    Modern SaaS KPI card with:
    • Soft colour fill + coloured top border
    • Icon pill on the left
    • Large bold value, short label, optional subtitle
    • Drop shadow
    • Hover background transition
    """

    def __init__(self, icon, label, value, accent, bg, border_col, subtitle=None):
        super().__init__()
        self.setObjectName('kpi_card')
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(96 if subtitle else 84)
        self._accent     = accent
        self._bg_default = bg
        self._bg_hover   = self._lighten(bg)
        self._border     = border_col
        self._apply_style(bg)
        _shadow(self)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(12)

        # Icon pill
        ico = QLabel(icon)
        ico.setFixedSize(38, 38)
        ico.setAlignment(Qt.AlignCenter)
        ico.setStyleSheet(
            f'background:white; border-radius:10px; font-size:18px;'
            f' border:1px solid {border_col};'
        )
        _shadow(ico, blur=6, offset_y=1, opacity=0.06)

        # Text column
        col = QVBoxLayout(); col.setSpacing(2)
        self._val = QLabel(str(value))
        self._val.setStyleSheet(
            f'color:{accent}; font-size:20px; font-weight:800;'
            f' background:transparent; letter-spacing:-0.5px;'
        )
        lbl_w = QLabel(label)
        lbl_w.setStyleSheet(
            f'color:#64748B; font-size:10px; font-weight:600;'
            f' background:transparent; letter-spacing:0.3px;'
        )
        col.addWidget(self._val)
        col.addWidget(lbl_w)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setStyleSheet('color:#94A3B8; font-size:8px; background:transparent;')
            col.addWidget(sub)

        outer.addWidget(ico)
        outer.addLayout(col)
        outer.addStretch()

    def _apply_style(self, bg):
        self.setStyleSheet(f'''
            QFrame#kpi_card {{
                background: {bg};
                border: 1px solid {self._border};
                border-top: 3px solid {self._accent};
                border-radius: 12px;
            }}
        ''')

    @staticmethod
    def _lighten(hex_col):
        """Return a slightly lighter version of a hex colour."""
        try:
            r = int(hex_col[1:3], 16); g = int(hex_col[3:5], 16); b = int(hex_col[5:7], 16)
            r = min(255, r + 12); g = min(255, g + 12); b = min(255, b + 12)
            return f'#{r:02X}{g:02X}{b:02X}'
        except Exception:
            return hex_col

    def enterEvent(self, e):
        self._apply_style(self._bg_hover); super().enterEvent(e)

    def leaveEvent(self, e):
        self._apply_style(self._bg_default); super().leaveEvent(e)

    def set_value(self, v):
        self._val.setText(str(v))


def _sec_header(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        'color:#94A3B8; font-size:9px; font-weight:700;'
        ' letter-spacing:1.2px; background:transparent; padding:4px 0 2px 2px;'
    )
    return lbl


def _divider() -> QFrame:
    f = QFrame(); f.setFrameShape(QFrame.HLine)
    f.setStyleSheet('color:#E2E8F0; background:#E2E8F0; max-height:1px; margin:4px 0;')
    return f


def _chart_frame(title: str, subtitle: str = '') -> tuple:
    """Return (QFrame, inner_layout) with title header."""
    frame = QFrame()
    frame.setStyleSheet(
        'QFrame{background:white;border:1px solid #E2E8F0;border-radius:14px;}'
    )
    _shadow(frame, blur=14, offset_y=4, opacity=0.06)
    outer = QVBoxLayout(frame)
    outer.setContentsMargins(16, 14, 16, 12)
    outer.setSpacing(6)

    hdr = QHBoxLayout(); hdr.setSpacing(8)
    t = QLabel(title)
    t.setStyleSheet(
        'color:#1E293B; font-size:12px; font-weight:700; background:transparent;'
    )
    hdr.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setStyleSheet(
            'color:#94A3B8; font-size:9px; background:transparent;'
        )
        hdr.addWidget(s)
    hdr.addStretch()
    outer.addLayout(hdr)

    inner = QVBoxLayout()
    inner.setContentsMargins(0, 0, 0, 0)
    outer.addLayout(inner, 1)
    frame.setMinimumHeight(230)
    return frame, inner


# ══════════════════════════════════════════════════════════════════════════════
#  DashboardWidget
# ══════════════════════════════════════════════════════════════════════════════

class DashboardWidget(QWidget):

    def __init__(self, session):
        super().__init__()
        self.session = session
        self.setStyleSheet('background:transparent;')
        self._cache  = {}       # chart data cache
        self._setup_ui()
        # Defer initial load so window is visible first
        QTimer.singleShot(80, self._load_data)
        # Auto-refresh every 90 s
        self._auto = QTimer(self)
        self._auto.setInterval(90_000)
        self._auto.timeout.connect(self.refresh)
        self._auto.start()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            'QScrollArea{border:none;background:transparent;}'
            'QScrollBar:vertical{width:6px;background:#F1F5F9;border-radius:3px;}'
            'QScrollBar::handle:vertical{background:#CBD5E1;border-radius:3px;min-height:24px;}'
        )
        root = QWidget(); root.setStyleSheet('background:transparent;')
        vl = QVBoxLayout(root)
        vl.setContentsMargins(24, 18, 24, 28)
        vl.setSpacing(14)
        self._vl = vl

        # ── Top bar: title + refresh ──────────────────────────────────────────
        top = QHBoxLayout(); top.setSpacing(12)
        title = QLabel('Tableau de Bord')
        title.setStyleSheet(
            'color:#0F172A; font-size:20px; font-weight:800;'
            ' background:transparent; letter-spacing:-0.5px;'
        )
        top.addWidget(title)
        top.addStretch()
        rfsh = QPushButton('↺  Actualiser')
        rfsh.setFixedHeight(32)
        rfsh.setCursor(Qt.PointingHandCursor)
        rfsh.setStyleSheet(
            'QPushButton{background:white;color:#475569;border:1.5px solid #E2E8F0;'
            'border-radius:8px;padding:0 16px;font-size:11px;font-weight:600;}'
            'QPushButton:hover{background:#F8FAFC;border-color:#CBD5E1;}'
        )
        rfsh.clicked.connect(self.refresh)
        top.addWidget(rfsh)
        vl.addLayout(top)

        # ── KPI grid: 4 groups ────────────────────────────────────────────────
        # Group headers + cards in one big 4-column grid
        # Col 0: Students (4 cards)
        # Col 1: Employee (1 card)
        # Col 2: Insurance (1 card)
        # Col 3: Profit (1 card)

        self._kpi_grid = QGridLayout()
        self._kpi_grid.setHorizontalSpacing(12)
        self._kpi_grid.setVerticalSpacing(6)
        self._kpi_grid.setContentsMargins(0, 0, 0, 0)
        for c in range(7): self._kpi_grid.setColumnStretch(c, 1)
        vl.addLayout(self._kpi_grid)

        # ── Charts section ────────────────────────────────────────────────────
        if HAS_MPL:
            vl.addWidget(_divider())

            # Annual profit (full width)
            self._annual = AnnualProfitChart(self.session)
            vl.addWidget(self._annual)

            # Row 1: Paid Students per Month | Paid Expenses per Month
            r1 = QHBoxLayout(); r1.setSpacing(12)
            self._ch1_f, self._ch1_l = _chart_frame(
                '✅  Élèves ayant payé par mois',
                'Nombre d\'élèves — mois scolaire'
            )
            self._ch2_f, self._ch2_l = _chart_frame(
                '💸  Dépenses payées par mois',
                'Montant total — mois scolaire'
            )
            r1.addWidget(self._ch1_f, 1)
            r1.addWidget(self._ch2_f, 1)
            vl.addLayout(r1)

            # Row 2: Students Registered per Month | (spare or class pie)
            r2 = QHBoxLayout(); r2.setSpacing(12)
            self._ch3_f, self._ch3_l = _chart_frame(
                '🎓  Élèves inscrits par mois',
                'Nombre d\'élèves — mois scolaire'
            )
            self._ch4_f, self._ch4_l = _chart_frame(
                '🎓  Répartition par classe',
                'Tous les élèves actifs'
            )
            r2.addWidget(self._ch3_f, 3)
            r2.addWidget(self._ch4_f, 2)
            vl.addLayout(r2)

        vl.addStretch()
        scroll.setWidget(root)
        ol = QVBoxLayout(self)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.addWidget(scroll)

    def _clear_chart(self, lay):
        for i in reversed(range(lay.count())):
            w = lay.itemAt(i).widget()
            if w: w.setParent(None)

    def _clear_kpi(self):
        for i in reversed(range(self._kpi_grid.count())):
            item = self._kpi_grid.itemAt(i)
            if item and item.widget(): item.widget().setParent(None)

    # ── Data ──────────────────────────────────────────────────────────────────

    def _load_data(self):
        self.session.expire_all()
        try:    self._render()
        except: import traceback; traceback.print_exc()

    def _render(self):
        cy  = datetime.now().year
        settings = {s.key: s.value for s in self.session.query(Setting).all()}
        sy  = settings.get('school_year', '2024-25')
        try: sy0, sy1 = int(sy.split('-')[0]), int(sy.split('-')[0]) + 1
        except: sy0, sy1 = cy - 1, cy

        month = _cur_school_month()
        pyear = (sy0 if (_SCHOOL_CAL.get(month, 1) >= 9) else sy1) if month else cy

        # ── Students ──────────────────────────────────────────────────────────
        students = self.session.query(Student).filter_by(active=True).all()
        n_total  = len(students)
        sid_map  = {s.id: s for s in students}

        recs = {}
        if month:
            for r in self.session.query(MonthRecord).filter_by(
                month_name=month, school_year=sy).all():
                recs[r.student_id] = r

        n_paid   = sum(1 for s in students if recs.get(s.id) and recs[s.id].status == 'paid')
        n_unpaid = sum(1 for s in students if recs.get(s.id) and recs[s.id].status == 'unpaid')

        all_unpaid = self.session.query(MonthRecord).filter_by(
            status='unpaid', school_year=sy).all()
        outstanding = sum(
            (sid_map[r.student_id].monthly_fee or 0)
            + ((sid_map[r.student_id].transport_fee or 0) if sid_map[r.student_id].has_transport else 0)
            for r in all_unpaid if r.student_id in sid_map
        )

        # ── Employees ─────────────────────────────────────────────────────────
        n_emp = self.session.query(Employee).filter_by(active=True).count()

        # ── Insurance (school year Nov–Jun) ───────────────────────────────────
        ins_total = sum(
            p.amount or 0.0
            for p in self.session.query(Payment).filter_by(
                payment_type='insurance', school_year=sy).all()
        )
        ins_sub = f'Année {sy}  •  Nov – Jun'

        # ── Revenue (current month, no insurance) ─────────────────────────────
        collected = sum(
            p.amount or 0
            for p in self.session.query(Payment).filter(
                Payment.payment_type.in_(['monthly', 'transport']),
                Payment.month == month,
                Payment.school_year == sy,
            ).all()
        ) if month else 0.0

        # ── Expenses (current month, paid only) ───────────────────────────────
        exp_paid = sum(
            ep.amount or 0
            for ep in self.session.query(ExpensePayment).filter_by(
                month=month, year=pyear).all()
        ) if month else 0.0

        # ── Salaries (current month, paid only) ───────────────────────────────
        sal_amt = 0.0
        if month:
            for sal in self.session.query(Salary).filter_by(month=month).all():
                if not getattr(sal, 'paid', False): continue
                yr = getattr(sal, 'year', None)
                if yr and yr not in (sy0, sy1): continue
                sal_amt += sal.net_salary or getattr(sal, 'total', 0) or 0.0

        # ── Profit ────────────────────────────────────────────────────────────
        profit    = collected - exp_paid - sal_amt
        prof_sign = '+' if profit > 0 else ''
        prof_col  = C_PROF if profit >= 0 else C_LOSS
        prof_bg   = C_PROF_BG if profit >= 0 else C_LOSS_BG
        prof_bd   = C_PROF_BD if profit >= 0 else C_LOSS_BD
        prof_sub  = f'Rev {_fmt_mad(collected)} − Dep {_fmt_mad(exp_paid)} − Sal {_fmt_mad(sal_amt)}'

        debt_col = C_LOSS   if outstanding > 50000 else ('#F59E0B' if outstanding > 0 else C_PROF)
        debt_bg  = C_LOSS_BG if outstanding > 50000 else (C_INS_BG  if outstanding > 0 else C_PROF_BG)
        debt_bd  = C_LOSS_BD if outstanding > 50000 else (C_INS_BD  if outstanding > 0 else C_PROF_BD)

        # ── Render KPI grid ───────────────────────────────────────────────────
        self._clear_kpi()
        g = self._kpi_grid

        # Section headers  (row 0)
        for col, txt in [
            (0, '👤  ÉLÈVES'), (4, '👔  EMPLOYÉS'),
            (5, '🛡  ASSURANCE'), (6, '📈  BÉNÉFICE'),
        ]:
            g.addWidget(_sec_header(txt), 0, col)

        # Row 1: Students (4) | Employee (1) | Insurance (1) | Profit (1)
        g.addWidget(KpiCard('👥','Total élèves',     n_total,          C_STUD,   C_STUD_BG,  C_STUD_BD),  1,0)
        g.addWidget(KpiCard('✅','Payés ce mois',    n_paid,           '#22C55E',C_PROF_BG,  C_PROF_BD),  1,1)
        g.addWidget(KpiCard('⏳','Non payés ce mois',n_unpaid,         C_LOSS,   C_LOSS_BG,  C_LOSS_BD),  1,2)
        g.addWidget(KpiCard('💳','Créances totales', _fmt_mad(outstanding),
                             debt_col, debt_bg, debt_bd),                                                 1,3)
        g.addWidget(KpiCard('👔','Total employés',   n_emp,            C_EMP,    C_EMP_BG,   C_EMP_BD,
                             subtitle='Actifs'),                                                           1,4)
        g.addWidget(KpiCard('🛡','Assurance (année)',_fmt_mad(ins_total),
                             C_INS, C_INS_BG, C_INS_BD, subtitle=ins_sub),                               1,5)
        g.addWidget(KpiCard('📈','Bénéfice du mois', prof_sign + _fmt_mad(profit),
                             prof_col, prof_bg, prof_bd, subtitle=prof_sub),                              1,6)

        # ── Cache chart data + draw ───────────────────────────────────────────
        if HAS_MPL:
            self._build_cache(sy, sy0, sy1)
            if hasattr(self, '_annual'): self._annual.refresh()
            self._draw_paid_students(sy)
            self._draw_paid_expenses(sy0, sy1)
            self._draw_student_registrations(sy)
            self._draw_class_pie()

    # ── Chart cache ───────────────────────────────────────────────────────────

    def _build_cache(self, sy, sy0, sy1):
        """Build all per-school-month arrays in one pass each."""
        paid_count  = [0]  * 10   # Chart 1: paid students per school month
        exp_total   = [0.0]* 10   # Chart 2: paid expenses per school month
        reg_count   = [0]  * 10   # Chart 3: registered students per school month

        # Chart 1 — paid MonthRecords per school month
        for r in self.session.query(MonthRecord).filter_by(
            status='paid', school_year=sy
        ).all():
            try: paid_count[SCHOOL_MONTHS.index(r.month_name)] += 1
            except: pass

        # Chart 2 — paid expenses per school month
        for ep in self.session.query(ExpensePayment).all():
            try:
                idx = SCHOOL_MONTHS.index(ep.month)
                expected_yr = sy0 if idx <= 3 else sy1
                if ep.year == expected_yr:
                    exp_total[idx] += ep.amount or 0
            except: pass

        # Chart 3 — count students with a MonthRecord (any status except nan)
        # per school month → proxy for "registered / enrolled this month"
        for r in self.session.query(MonthRecord).filter(
            MonthRecord.school_year == sy,
            MonthRecord.status != 'nan',
        ).all():
            try: reg_count[SCHOOL_MONTHS.index(r.month_name)] += 1
            except: pass

        self._cache = {
            'paid_count': paid_count,
            'exp_total':  exp_total,
            'reg_count':  reg_count,
        }

    # ── Chart helpers ─────────────────────────────────────────────────────────

    def _make_fig(self, w=6, h=2.6):
        fig = Figure(figsize=(w, h), facecolor='white')
        fig.subplots_adjust(left=0.08, right=0.97, top=0.82, bottom=0.16)
        return fig

    def _style_ax(self, ax, xs, labels, y_int=False):
        ax.set_facecolor(C_CHART_BG)
        ax.set_xticks(list(xs))
        ax.set_xticklabels(labels, fontsize=7.5)
        for t in ax.get_xticklabels(): t.set_color('#64748B')
        ax.yaxis.set_tick_params(labelcolor='#64748B', labelsize=7.5)
        if y_int:
            ax.yaxis.set_major_formatter(
                matplotlib.ticker.FuncFormatter(lambda v, _: f'{int(v)}')
            )
        else:
            ax.yaxis.set_major_formatter(
                matplotlib.ticker.FuncFormatter(
                    lambda v, _: f'{v/1000:.0f}k' if abs(v) >= 1000 else f'{v:.0f}'
                )
            )
        for sp in ax.spines.values(): sp.set_visible(False)
        ax.yaxis.grid(True, color=C_GRID, linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)

    # ── Chart 1: Paid students per month ──────────────────────────────────────

    def _draw_paid_students(self, sy):
        self._clear_chart(self._ch1_l)
        data = self._cache.get('paid_count', [0]*10)

        fig = self._make_fig()
        ax  = fig.add_subplot(111)
        bars = ax.bar(range(10), data, color=C_STUD, width=0.55,
                      zorder=3, alpha=0.88)
        # Value labels on bars
        for bar, v in zip(bars, data):
            if v > 0:
                ax.text(bar.get_x() + bar.get_width()/2, v + 0.2,
                        str(v), ha='center', fontsize=6.5,
                        fontweight='600', color=C_STUD, zorder=5)
        self._style_ax(ax, range(10), _SHORT, y_int=True)
        ax.set_ylim(0, max(data) * 1.18 + 1 if any(data) else 5)
        fig.tight_layout(pad=0.8)
        cv = FigureCanvas(fig); cv.setStyleSheet('background:white;')
        self._ch1_l.addWidget(cv)

    # ── Chart 2: Paid expenses per month ──────────────────────────────────────

    def _draw_paid_expenses(self, sy0, sy1):
        self._clear_chart(self._ch2_l)
        data = self._cache.get('exp_total', [0.0]*10)

        fig = self._make_fig()
        ax  = fig.add_subplot(111)
        bars = ax.bar(range(10), data, color=C_EXP, width=0.55,
                      zorder=3, alpha=0.85)
        for bar, v in zip(bars, data):
            if v > 0:
                lbl = f'{v/1000:.1f}k' if v >= 1000 else f'{v:.0f}'
                ax.text(bar.get_x() + bar.get_width()/2, v + max(data)*0.01 + 1,
                        lbl, ha='center', fontsize=6.5,
                        fontweight='600', color=C_EXP, zorder=5)
        self._style_ax(ax, range(10), _SHORT)
        ax.set_ylim(0, max(data) * 1.18 + 1 if any(data) else 100)
        fig.tight_layout(pad=0.8)
        cv = FigureCanvas(fig); cv.setStyleSheet('background:white;')
        self._ch2_l.addWidget(cv)

    # ── Chart 3: Students registered per month ────────────────────────────────

    def _draw_student_registrations(self, sy):
        self._clear_chart(self._ch3_l)
        data = self._cache.get('reg_count', [0]*10)
        xs   = range(10)

        fig = self._make_fig(w=8)
        ax  = fig.add_subplot(111)
        ax.fill_between(xs, data, alpha=0.12, color=C_STUD)
        ax.plot(xs, data, color=C_STUD, lw=2.2, zorder=3,
                marker='o', ms=5, markerfacecolor='white',
                markeredgewidth=2, markeredgecolor=C_STUD)
        for i, v in enumerate(data):
            if v > 0:
                ax.text(i, v + max(data)*0.03 + 0.2, str(v),
                        ha='center', fontsize=6.5,
                        fontweight='600', color=C_STUD, zorder=5)
        self._style_ax(ax, xs, _SHORT, y_int=True)
        ax.set_ylim(0, max(data) * 1.22 + 1 if any(data) else 5)
        fig.tight_layout(pad=0.8)
        cv = FigureCanvas(fig); cv.setStyleSheet('background:white;')
        self._ch3_l.addWidget(cv)

    # ── Chart 4: Class breakdown pie ──────────────────────────────────────────

    def _draw_class_pie(self):
        self._clear_chart(self._ch4_l)
        counts, labels = [], []
        for cls in CLASSES:
            n = self.session.query(Student).filter_by(
                class_name=cls, active=True).count()
            if n: counts.append(n); labels.append(cls)
        if not counts: counts, labels = [1], ['Aucun']

        pal = ['#0EA5E9','#8B5CF6','#10B981','#F59E0B','#EF4444',
               '#6366F1','#14B8A6','#EC4899','#22C55E','#F97316']
        fig = Figure(figsize=(4, 2.5), facecolor='white')
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        ax  = fig.add_subplot(111)
        ax.pie(counts, labels=labels, autopct='%1.0f%%',
               colors=pal[:len(counts)],
               textprops={'fontsize':7,'color':'#374151'},
               pctdistance=0.78,
               wedgeprops={'linewidth':1.5,'edgecolor':'white'})
        cv = FigureCanvas(fig); cv.setStyleSheet('background:white;')
        self._ch4_l.addWidget(cv)

    # ── Public ────────────────────────────────────────────────────────────────

    def refresh(self):
        self._cache = {}
        self._load_data()


class AnnualProfitChart(QWidget):
    """
    Full-width Monthly Profit Evolution chart — Jan to Dec.

    Formula per calendar month:
        Profit = Revenue(monthly + transport) − Expenses − Salaries
        Insurance is EXCLUDED.

    Features
    ─────────
    • 12-month calendar bar chart (Jan–Dec)
    • Cumulative profit dashed line overlay
    • Current month highlighted with indigo border + ▼ marker
    • Future months greyed out (no phantom projections)
    • Value labels on every meaningful bar
    • Summary stats row: best month / worst month / YTD cumulative
    • Year selector (current year ± 3)
    • Manual ↺ refresh button + timestamp
    • Auto-refresh every 60 s via QTimer (re-queries DB silently)
    • DashboardWidget calls .refresh() after every payment/expense/salary event
    • Hover tooltip via mpl motion_notify_event (shows breakdown)
    """

    AUTO_REFRESH_MS = 60_000   # 1 minute

    def __init__(self, session):
        super().__init__()
        self.session   = session
        self._canvas   = None
        self._fig      = None
        self._bars     = []
        self._data     = {}     # cached: {year: (rev, exp, sal, prf)}
        self.setStyleSheet('background:transparent;')
        self._build_ui()
        # Defer first draw so the widget is fully shown before matplotlib renders
        QTimer.singleShot(150, self.refresh)
        # Auto-refresh timer
        self._timer = QTimer(self)
        self._timer.setInterval(self.AUTO_REFRESH_MS)
        self._timer.timeout.connect(self._silent_refresh)
        self._timer.start()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Card shell ────────────────────────────────────────────────────────
        self._card = QFrame()
        self._card.setStyleSheet(
            f'QFrame{{'
            f'background:{BG_CARD};'
            f'border:1px solid {BORDER};'
            f'border-radius:12px;'
            f'}}'
        )
        self._card.setMinimumHeight(340)
        card_lay = QVBoxLayout(self._card)
        card_lay.setContentsMargins(18, 14, 18, 12)
        card_lay.setSpacing(8)

        # ── Header row ────────────────────────────────────────────────────────
        hdr = QHBoxLayout(); hdr.setSpacing(10)

        # Icon + title stack
        icon_lbl = QLabel('📈')
        icon_lbl.setFixedSize(36, 36)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(
            f'background:{SUCCESS_LIGHT};border-radius:10px;font-size:17px;'
        )

        title_col = QVBoxLayout(); title_col.setSpacing(1)
        t1 = QLabel('Évolution du Bénéfice Mensuel')
        t1.setStyleSheet(
            f'color:{TEXT_MAIN};font-size:14px;font-weight:800;background:transparent;'
        )
        t2 = QLabel(
            'Revenus + Transport  −  Dépenses  −  Salaires   ·   '
            'Assurance exclue   ·   Jan – Déc'
        )
        t2.setStyleSheet(
            f'color:{TEXT_SUB};font-size:9.5px;background:transparent;'
        )
        title_col.addWidget(t1); title_col.addWidget(t2)

        hdr.addWidget(icon_lbl)
        hdr.addLayout(title_col)
        hdr.addStretch()

        # Year selector
        _lbl_yr = QLabel('Année :')
        _lbl_yr.setStyleSheet(
            f'color:{TEXT_SUB};font-size:11px;font-weight:600;background:transparent;'
        )
        combo_css = (
            f'QComboBox{{background:{PRIMARY_LIGHT};border:1.5px solid {PRIMARY}33;'
            f'border-radius:8px;color:{PRIMARY};padding:3px 10px;'
            f'font-size:12px;font-weight:700;min-width:80px;}}'
            f'QComboBox::drop-down{{border:none;width:18px;}}'
            f'QComboBox QAbstractItemView{{background:white;border:1px solid {BORDER};'
            f'color:{TEXT_MAIN};outline:none;border-radius:6px;}}'
            f'QComboBox QAbstractItemView::item{{padding:6px 12px;}}'
            f'QComboBox QAbstractItemView::item:selected'
            f'{{background:{PRIMARY_LIGHT};color:{PRIMARY};}}'
        )
        self._yr_combo = QComboBox()
        self._yr_combo.setStyleSheet(combo_css)
        self._yr_combo.setFixedHeight(30)
        cy = datetime.now().year
        for y in range(cy - 3, cy + 2):
            self._yr_combo.addItem(str(y), y)
        self._yr_combo.setCurrentIndex(3)   # current year
        self._yr_combo.currentIndexChanged.connect(self.refresh)

        # Refresh button
        rfsh_btn = QPushButton('↺')
        rfsh_btn.setFixedSize(30, 30)
        rfsh_btn.setToolTip('Actualiser maintenant')
        rfsh_btn.setStyleSheet(
            f'QPushButton{{background:{SUCCESS_LIGHT};color:{SUCCESS};border:none;'
            f'border-radius:8px;font-size:15px;font-weight:700;}}'
            f'QPushButton:hover{{background:{SUCCESS};color:white;}}'
        )
        rfsh_btn.clicked.connect(self.refresh)

        self._ts_lbl = QLabel('')
        self._ts_lbl.setStyleSheet(
            'color:#9CA3AF;font-size:9px;background:transparent;'
        )

        for w in [_lbl_yr, self._yr_combo, rfsh_btn, self._ts_lbl]:
            hdr.addWidget(w)

        card_lay.addLayout(hdr)

        # ── Summary stats strip ───────────────────────────────────────────────
        self._stats_row = QHBoxLayout()
        self._stats_row.setSpacing(12)
        self._stats_row.setContentsMargins(4, 0, 4, 0)
        # Placeholders — filled in after first draw
        self._stat_widgets = []
        for _ in range(4):
            lbl = QLabel('—')
            lbl.setStyleSheet(
                f'color:{TEXT_SUB};font-size:10px;background:transparent;'
            )
            self._stats_row.addWidget(lbl)
            self._stat_widgets.append(lbl)
        self._stats_row.addStretch()
        card_lay.addLayout(self._stats_row)

        # ── Chart area ────────────────────────────────────────────────────────
        self._chart_lay = QVBoxLayout()
        self._chart_lay.setContentsMargins(0, 0, 0, 0)
        self._chart_lay.setSpacing(0)

        self._placeholder = QLabel('Chargement du graphique…')
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(
            'color:#D1D5DB;font-size:13px;background:transparent;padding:40px;'
        )
        self._chart_lay.addWidget(self._placeholder)
        card_lay.addLayout(self._chart_lay, 1)

        outer.addWidget(self._card)

    # ── Stat strip helpers ────────────────────────────────────────────────────

    def _update_stats(self, year, prf, is_cy, cm):
        realized = [v for i, v in enumerate(prf) if not (is_cy and i > cm)]
        if not realized:
            return
        ytd       = sum(realized)
        best_i    = prf.index(max(prf))
        worst_i   = prf.index(min(prf))
        avg       = sum(realized) / len(realized) if realized else 0

        def _f(v):
            sign = '+' if v > 0 else ''
            if abs(v) >= 1_000_000: return f'{sign}{v/1_000_000:.2f}M MAD'
            if abs(v) >= 1_000:     return f'{sign}{v/1_000:.1f}k MAD'
            return f'{sign}{v:.0f} MAD'

        stats = [
            (f'Cumul {year} : {_f(ytd)}',
             SUCCESS if ytd >= 0 else DANGER),
            (f'Meilleur mois : {_SHORT_CAL[best_i]}  {_f(max(prf))}',
             SUCCESS),
            (f'Pire mois : {_SHORT_CAL[worst_i]}  {_f(min(prf))}',
             DANGER),
            (f'Moyenne / mois : {_f(avg)}',
             TEXT_SUB),
        ]
        for lbl, (text, color) in zip(self._stat_widgets, stats):
            lbl.setText(text)
            lbl.setStyleSheet(
                f'color:{color};font-size:10px;font-weight:600;background:transparent;'
            )

    # ── Data computation ──────────────────────────────────────────────────────

    def _compute(self, year: int):
        """
        Returns (rev, exp, sal, prf) — 12-element lists indexed 0=Jan … 11=Dec.
        Two-layer fallback for each source:
          1. payment_date / paid_date  (real recorded date)
          2. Payment.year + Payment.month name mapped to calendar month
        Insurance is always excluded from revenue.
        """
        rev = [0.0] * 12
        exp = [0.0] * 12
        sal = [0.0] * 12

        # Revenue: monthly + transport payments only
        for p in self.session.query(Payment).filter(
            Payment.payment_type.in_(['monthly', 'transport'])
        ).all():
            try:
                if p.payment_date and p.payment_date.year == year:
                    rev[p.payment_date.month - 1] += p.amount or 0
                elif (p.year == year) and p.month:
                    cal = _SCHOOL_CAL.get(p.month, 0)
                    if cal: rev[cal - 1] += p.amount or 0
            except Exception:
                pass

        # Expenses
        for ep in self.session.query(ExpensePayment).filter_by(year=year).all():
            try:
                cal = _SCHOOL_CAL.get(ep.month or '', 0)
                if cal: exp[cal - 1] += ep.amount or 0
            except Exception:
                pass

        # Salaries — null-safe paid check
        for s in self.session.query(Salary).all():
            try:
                if not getattr(s, 'paid', True):
                    continue
                amt = s.net_salary or getattr(s, 'total', 0) or 0
                if s.paid_date and s.paid_date.year == year:
                    sal[s.paid_date.month - 1] += amt
                elif (s.year == year) and s.month:
                    cal = _SCHOOL_CAL.get(s.month, 0)
                    if cal: sal[cal - 1] += amt
            except Exception:
                pass

        prf = [rev[i] - exp[i] - sal[i] for i in range(12)]
        return rev, exp, sal, prf

    # ── Refresh entry points ──────────────────────────────────────────────────

    def refresh(self):
        """Full refresh: expire session, clear cache for this year, redraw."""
        self.session.expire_all()
        year = self._yr_combo.currentData() or datetime.now().year
        self._data.pop(year, None)   # invalidate cache
        self._draw_year(year)

    def _silent_refresh(self):
        """Timer-triggered: expire + redraw without clearing cache indicator."""
        self.session.expire_all()
        year = self._yr_combo.currentData() or datetime.now().year
        self._data.pop(year, None)
        self._draw_year(year)

    def _draw_year(self, year: int):
        if year not in self._data:
            try:
                self._data[year] = self._compute(year)
            except Exception:
                import traceback; traceback.print_exc()
                return
        rev, exp, sal, prf = self._data[year]
        self._draw(year, rev, exp, sal, prf)

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self, year, rev, exp, sal, prf):
        # Remove old canvas
        if self._canvas:
            self._canvas.mpl_disconnect(self._cid) if hasattr(self, '_cid') else None
            self._canvas.setParent(None)
            self._canvas = None
        if self._placeholder:
            self._placeholder.setParent(None)
            self._placeholder = None
        for i in reversed(range(self._chart_lay.count())):
            w = self._chart_lay.itemAt(i).widget()
            if w: w.setParent(None)

        now    = datetime.now()
        cm     = now.month - 1        # 0-based current month index
        cy     = now.year
        is_cy  = (year == cy)

        # ── Figure ────────────────────────────────────────────────────────────
        fig = Figure(figsize=(13, 3.5), facecolor='white')
        fig.subplots_adjust(left=0.055, right=0.975, top=0.84, bottom=0.14)
        ax = fig.add_subplot(111)
        ax.set_facecolor('white')

        xs = list(range(12))
        W  = 0.62

        # ── Bar colours ───────────────────────────────────────────────────────
        face_c, edge_c, lw_v, alpha_v = [], [], [], []
        for i, v in enumerate(prf):
            is_cur  = is_cy and i == cm
            is_fut  = is_cy and i > cm
            is_zero = (rev[i] == 0 and exp[i] == 0 and sal[i] == 0)

            if is_fut and is_zero:
                fc, ec = '#F3F4F6', '#E5E7EB'
            elif v >= 0:
                fc, ec = '#10B981', '#059669'
            else:
                fc, ec = '#EF4444', '#DC2626'

            face_c.append(fc)
            edge_c.append('#4F46E5' if is_cur else ec)
            lw_v.append(2.4 if is_cur else 0.6)
            alpha_v.append(0.35 if (is_fut and is_zero) else 1.0)

        # ── Draw bars ─────────────────────────────────────────────────────────
        self._bars = ax.bar(
            xs, prf,
            color=face_c, edgecolor=edge_c, linewidth=lw_v,
            width=W, zorder=3
        )
        for bar, alph in zip(self._bars, alpha_v):
            bar.set_alpha(alph)

        # ── Zero baseline ─────────────────────────────────────────────────────
        ax.axhline(0, color='#CBD5E1', linewidth=0.8, zorder=2)

        # ── Cumulative line (up to current month only) ────────────────────────
        cx_pts, cy_pts, run = [], [], 0.0
        for i, v in enumerate(prf):
            if is_cy and i > cm:
                break
            run += v
            cx_pts.append(i)
            cy_pts.append(run)

        if len(cx_pts) > 1:
            ax.plot(
                cx_pts, cy_pts,
                color='#4F46E5', linewidth=2.0, linestyle='--',
                zorder=4, alpha=0.85,
                marker='o', markersize=3.0,
                markerfacecolor='white', markeredgewidth=1.4,
                markeredgecolor='#4F46E5',
                label='Cumul annuel',
            )

        # ── Value labels ──────────────────────────────────────────────────────
        mx = max((abs(v) for v in prf), default=1) or 1
        for i, (bar, v) in enumerate(zip(self._bars, prf)):
            if is_cy and i > cm and abs(v) < 1:
                continue
            if abs(v) < mx * 0.02:   # skip tiny bars — avoid clutter
                continue
            txt = (f'{v/1_000_000:.2f}M' if abs(v) >= 1_000_000
                   else f'{v/1_000:.1f}k' if abs(v) >= 1_000
                   else f'{v:.0f}')
            y_off = 4 if v >= 0 else -11
            ax.annotate(
                txt,
                xy=(bar.get_x() + bar.get_width() / 2, v),
                xytext=(0, y_off),
                textcoords='offset points',
                ha='center', fontsize=6.5, fontweight='600',
                color='#059669' if v >= 0 else '#DC2626',
                zorder=5,
            )

        # ── Current month marker ──────────────────────────────────────────────
        if is_cy and 0 <= cm < 12:
            ax.annotate(
                '▼  Maintenant',
                xy=(cm, max(prf[cm], 0)),
                xytext=(0, 12),
                textcoords='offset points',
                ha='center', fontsize=7, fontweight='700',
                color='#4F46E5',
            )

        # ── X axis ────────────────────────────────────────────────────────────
        ax.set_xticks(xs)
        ax.set_xticklabels(_SHORT_CAL, fontsize=8.5)
        for i, tick in enumerate(ax.get_xticklabels()):
            is_cur = is_cy and i == cm
            tick.set_color('#4F46E5' if is_cur else '#6B7280')
            tick.set_fontweight('bold' if is_cur else 'normal')
            tick.set_fontsize(9 if is_cur else 8)

        # ── Y axis ────────────────────────────────────────────────────────────
        ax.yaxis.set_tick_params(labelcolor='#9CA3AF', labelsize=8)
        ax.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(
                lambda v, _: (
                    f'{v/1_000_000:.1f}M' if abs(v) >= 1_000_000
                    else f'{v/1_000:.0f}k' if abs(v) >= 1_000
                    else f'{v:.0f}'
                )
            )
        )
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.yaxis.grid(True, color='#F3F4F8', linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)

        # ── Figure title (right-aligned cumulative) ───────────────────────────
        realized = [v for i, v in enumerate(prf) if not (is_cy and i > cm)]
        ytd = sum(realized)
        t_col  = '#059669' if ytd >= 0 else '#DC2626'
        t_sign = '+' if ytd > 0 else ''
        if abs(ytd) >= 1_000_000:
            t_lbl = f'{t_sign}{ytd/1_000_000:.2f}M MAD'
        elif abs(ytd) >= 1_000:
            t_lbl = f'{t_sign}{ytd/1_000:.1f}k MAD'
        else:
            t_lbl = f'{t_sign}{ytd:.0f} MAD'

        ax.set_title(
            f'Bénéfice {year}  ·  YTD : {t_lbl}',
            fontsize=9.5, fontweight='800',
            color=t_col, pad=6, loc='right',
        )

        # ── Legend ────────────────────────────────────────────────────────────
        legend_handles = [
            Patch(facecolor='#10B981', edgecolor='#059669',
                  label='Bénéfice positif'),
            Patch(facecolor='#EF4444', edgecolor='#DC2626',
                  label='Bénéfice négatif'),
            Line2D([0], [0], color='#4F46E5', linewidth=1.8,
                   linestyle='--', marker='o', markersize=3,
                   label='Cumul annuel'),
            Patch(facecolor='#F3F4F6', edgecolor='#E5E7EB',
                  label='Données non disponibles'),
        ]
        ax.legend(
            handles=legend_handles,
            fontsize=7.5, frameon=False,
            loc='upper left', ncol=4,
        )

        # ── Hover tooltip ─────────────────────────────────────────────────────
        annot = ax.annotate(
            '', xy=(0, 0),
            xytext=(12, 12), textcoords='offset points',
            bbox=dict(boxstyle='round,pad=0.5', fc='white',
                      ec='#E5E7EB', lw=1.0, alpha=0.95),
            fontsize=8,
            arrowprops=dict(arrowstyle='->', color='#9CA3AF', lw=0.8),
        )
        annot.set_visible(False)

        def _on_hover(event):
            if event.inaxes != ax:
                annot.set_visible(False)
                fig.canvas.draw_idle()
                return
            for i, bar in enumerate(self._bars):
                if bar.contains(event)[0]:
                    r_str = _fmt_mad_signed(rev[i])
                    e_str = _fmt_mad_signed(-exp[i])
                    s_str = _fmt_mad_signed(-sal[i])
                    p_str = _fmt_mad_signed(prf[i])
                    annot.set_text(
                        f'{_SHORT_CAL[i]}\n'
                        f'Rev  {r_str}\n'
                        f'Dep  {e_str}\n'
                        f'Sal  {s_str}\n'
                        f'───────\n'
                        f'= {p_str}'
                    )
                    annot.xy = (
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height() if prf[i] >= 0 else 0,
                    )
                    annot.set_visible(True)
                    fig.canvas.draw_idle()
                    return
            annot.set_visible(False)
            fig.canvas.draw_idle()

        self._fig = fig
        canvas = FigureCanvas(fig)
        canvas.setStyleSheet('background:white;border-radius:8px;')
        canvas.setMinimumHeight(240)
        self._cid = canvas.mpl_connect('motion_notify_event', _on_hover)
        self._canvas = canvas
        self._chart_lay.addWidget(canvas)

        # Update stats strip
        self._update_stats(year, prf, is_cy, cm)

        # Timestamp
        self._ts_lbl.setText(f'↻ {now.strftime("%H:%M:%S")}')


def _fmt_mad_signed(v: float) -> str:
    sign = '+' if v > 0 else ''
    if abs(v) >= 1_000_000: return f'{sign}{v/1_000_000:.2f}M'
    if abs(v) >= 1_000:     return f'{sign}{v/1_000:.1f}k'
    return f'{sign}{v:.0f}'
