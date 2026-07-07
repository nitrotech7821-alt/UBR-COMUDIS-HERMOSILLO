import os
import re
from io import BytesIO
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import streamlit as st

try:
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    REPORTLAB_OK = True
except Exception:
    REPORTLAB_OK = False

# =====================================================
# CONFIGURACION GENERAL
# =====================================================
st.set_page_config(
    page_title="Sistema UBR DIF Hermosillo",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_DIR = "data"
DB_FILE = os.path.join(DATA_DIR, "registros_ubr.csv")
CAT_SERVICIOS = os.path.join(DATA_DIR, "catalogo_servicios.csv")
CAT_UBR = os.path.join(DATA_DIR, "catalogo_ubr.csv")
os.makedirs(DATA_DIR, exist_ok=True)

COLUMNAS = [
    "id", "fecha", "anio", "mes", "ubr", "area", "servicio",
    "servicios", "beneficiarios", "responsable", "observaciones", "origen"
]

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
MESES_NOMBRE = {v: k.capitalize() for k, v in MESES.items() if k != "setiembre"}

UBR_DEFAULT = ["HERMOSILLO", "PMA", "KINO"]
SERVICIOS_DEFAULT = [
    "Trabajo Social", "Sesiones Psicología", "Sesiones Terapia de Lenguaje",
    "Consultas Medicas", "Consulta Cámara Hiperbárica", "Consulta Neuropsicologo",
    "Consulta tanatologo", "Sesiones Terapia Física",
    "Sesiones Terapia Cámara Hiperbárica", "Terapia Ocupacional",
    "Terapia Sensorial", "Traslados", "Talleres y platicas de sensibilización",
    "Funcionales", "Prótesis", "Órtesis", "Otros"
]

# =====================================================
# ESTILOS
# =====================================================
st.markdown("""
<style>
.block-container {padding-top: 1.5rem; padding-bottom: 3rem;}
.main-header {
    background: linear-gradient(135deg, #7b1f4b 0%, #087d72 100%);
    padding: 32px 28px;
    border-radius: 18px;
    color: white;
    text-align: center;
    margin-bottom: 22px;
    box-shadow: 0 6px 18px rgba(0,0,0,.15);
}
.main-header h1 {font-size: 42px; margin: 0; font-weight: 800;}
.main-header p {font-size: 17px; margin: 8px 0 0 0;}
.kpi-card {
    background: white;
    padding: 18px;
    border-radius: 16px;
    border: 1px solid #e5e7eb;
    box-shadow: 0 2px 10px rgba(0,0,0,.06);
}
.kpi-title {font-size: 14px; color: #6b7280;}
.kpi-value {font-size: 32px; font-weight: 800; color: #111827;}
.section-title {font-size: 26px; font-weight: 800; margin-top: 12px;}
.success-box {background:#e8fff3; padding:15px; border-radius:12px; border:1px solid #9af0c4;}
.warning-box {background:#fff7ed; padding:15px; border-radius:12px; border:1px solid #fed7aa;}
</style>
""", unsafe_allow_html=True)

# =====================================================
# UTILIDADES
# =====================================================
def normalizar_texto(x):
    if pd.isna(x):
        return ""
    return str(x).strip()


def numero(x):
    if pd.isna(x) or x == "":
        return 0
    try:
        return int(float(str(x).replace(",", "").strip()))
    except Exception:
        return 0


def limpiar_servicio(x):
    txt = normalizar_texto(x)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def init_files():
    if not os.path.exists(DB_FILE):
        pd.DataFrame(columns=COLUMNAS).to_csv(DB_FILE, index=False)
    if not os.path.exists(CAT_UBR):
        pd.DataFrame({"ubr": UBR_DEFAULT}).to_csv(CAT_UBR, index=False)
    if not os.path.exists(CAT_SERVICIOS):
        pd.DataFrame({"servicio": SERVICIOS_DEFAULT}).to_csv(CAT_SERVICIOS, index=False)


def cargar_registros():
    init_files()
    df = pd.read_csv(DB_FILE)
    for col in COLUMNAS:
        if col not in df.columns:
            df[col] = "" if col not in ["servicios", "beneficiarios", "anio", "mes"] else 0
    if not df.empty:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.date
        df["servicios"] = pd.to_numeric(df["servicios"], errors="coerce").fillna(0).astype(int)
        df["beneficiarios"] = pd.to_numeric(df["beneficiarios"], errors="coerce").fillna(0).astype(int)
        df["anio"] = pd.to_numeric(df["anio"], errors="coerce").fillna(0).astype(int)
        df["mes"] = pd.to_numeric(df["mes"], errors="coerce").fillna(0).astype(int)
    return df[COLUMNAS]


def guardar_registros(df):
    os.makedirs(DATA_DIR, exist_ok=True)
    out = df.copy()
    out["fecha"] = pd.to_datetime(out["fecha"], errors="coerce").dt.strftime("%Y-%m-%d")
    out.to_csv(DB_FILE, index=False)


def cargar_catalogo(path, col, defaults):
    init_files()
    if os.path.exists(path):
        df = pd.read_csv(path)
        if col in df.columns:
            vals = [v for v in df[col].dropna().astype(str).str.strip().tolist() if v]
            return sorted(set(vals)) if vals else defaults
    return defaults


def next_id(df):
    if df.empty or "id" not in df.columns:
        return 1
    return int(pd.to_numeric(df["id"], errors="coerce").fillna(0).max()) + 1


def header():
    st.markdown("""
    <div class='main-header'>
        <h1>🏥 Sistema Integral de Servicios UBR</h1>
        <p>Captura, consulta, importación histórica y reportes mensuales DIF Hermosillo</p>
    </div>
    """, unsafe_allow_html=True)


def kpi(titulo, valor):
    st.markdown(f"""
    <div class='kpi-card'>
        <div class='kpi-title'>{titulo}</div>
        <div class='kpi-value'>{valor}</div>
    </div>
    """, unsafe_allow_html=True)


def filtrar_df(df, fecha_ini=None, fecha_fin=None, ubrs=None, servicios=None):
    f = df.copy()
    if f.empty:
        return f
    f["fecha"] = pd.to_datetime(f["fecha"], errors="coerce").dt.date
    if fecha_ini:
        f = f[f["fecha"] >= fecha_ini]
    if fecha_fin:
        f = f[f["fecha"] <= fecha_fin]
    if ubrs:
        f = f[f["ubr"].isin(ubrs)]
    if servicios:
        f = f[f["servicio"].isin(servicios)]
    return f

# =====================================================
# IMPORTADOR DEL EXCEL HISTORICO
# =====================================================
def detectar_ubr(sheet_name):
    s = sheet_name.lower()
    if "hermosillo" in s:
        return "HERMOSILLO"
    if "pma" in s or "miguel" in s:
        return "PMA"
    if "kino" in s:
        return "KINO"
    return "GENERAL"


def importar_excel_historico(uploaded_file, anio_default=2021):
    """
    Convierte el Excel concentrado anterior a registros mensuales.
    También acepta archivo tipo base de datos con columnas fecha, ubr y servicio.
    """
    registros = []
    xls = pd.ExcelFile(uploaded_file)

    for sheet in xls.sheet_names:
        raw = pd.read_excel(uploaded_file, sheet_name=sheet, header=None)
        raw = raw.dropna(how="all").dropna(axis=1, how="all")
        if raw.empty:
            continue

        # Caso 1: ya es base de datos con encabezados reales
        prueba = pd.read_excel(uploaded_file, sheet_name=sheet)
        cols = {str(c).strip().lower(): c for c in prueba.columns}
        if {"fecha", "ubr", "servicio"}.issubset(cols.keys()):
            for _, r in prueba.iterrows():
                fecha = pd.to_datetime(r[cols["fecha"]], errors="coerce")
                if pd.isna(fecha):
                    continue
                servicio = limpiar_servicio(r[cols["servicio"]])
                if not servicio:
                    continue
                registros.append({
                    "fecha": fecha.date(),
                    "anio": int(fecha.year),
                    "mes": int(fecha.month),
                    "ubr": normalizar_texto(r[cols["ubr"]]).upper(),
                    "area": normalizar_texto(r[cols.get("area", cols["servicio"])]),
                    "servicio": servicio,
                    "servicios": numero(r[cols.get("servicios", cols.get("cantidad", cols["servicio"]))]) if ("servicios" in cols or "cantidad" in cols) else 0,
                    "beneficiarios": numero(r[cols.get("beneficiarios", cols["servicio"])]) if "beneficiarios" in cols else 0,
                    "responsable": normalizar_texto(r[cols.get("responsable", cols["servicio"])]) if "responsable" in cols else "",
                    "observaciones": "Importado de base de datos Excel",
                    "origen": f"Excel - {sheet}",
                })
            continue

        ubr = detectar_ubr(sheet)
        if ubr == "GENERAL":
            # El concentrado general no trae mes, se importa como cierre anual si el usuario lo desea después.
            continue

        # Buscar fila que contiene meses
        header_row = None
        month_cols = []
        for idx, row in raw.iterrows():
            encontrados = []
            for c, val in row.items():
                txt = normalizar_texto(val).lower()
                txt = txt.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
                if txt in MESES:
                    encontrados.append((c, MESES[txt]))
            if encontrados:
                header_row = idx
                month_cols = encontrados
                break
        if header_row is None:
            continue

        # Año: buscar texto tipo Area 2021
        anio = anio_default
        texto_hoja = " ".join(raw.astype(str).fillna("").values.flatten().tolist())
        m = re.search(r"(20\d{2})", texto_hoja)
        if m:
            anio = int(m.group(1))

        # Columna del servicio normalmente es la anterior a la primera columna de mes
        first_month_col = min(c for c, _ in month_cols)
        service_col_candidates = [c for c in raw.columns if c < first_month_col]
        service_col = service_col_candidates[-1] if service_col_candidates else raw.columns[0]

        for r_index in range(header_row + 2, len(raw)):
            row = raw.iloc[r_index]
            servicio = limpiar_servicio(row.get(service_col, ""))
            if not servicio or servicio.upper() in ["TOTAL", "TOTALES"]:
                continue
            if servicio.lower().startswith("nan"):
                continue
            for col, mes_num in month_cols:
                # saltar totales si el mes no es válido no aplica, pero por seguridad
                servicios = numero(row.get(col, 0))
                beneficiarios = numero(row.get(col + 1, 0)) if (col + 1) in raw.columns else 0
                if servicios == 0 and beneficiarios == 0:
                    continue
                registros.append({
                    "fecha": date(anio, mes_num, 1),
                    "anio": anio,
                    "mes": mes_num,
                    "ubr": ubr,
                    "area": "Histórico Excel",
                    "servicio": servicio,
                    "servicios": servicios,
                    "beneficiarios": beneficiarios,
                    "responsable": "",
                    "observaciones": "Importado desde Excel concentrado histórico",
                    "origen": f"Excel histórico - {sheet}",
                })

    df = pd.DataFrame(registros)
    if df.empty:
        return pd.DataFrame(columns=COLUMNAS)
    return df

# =====================================================
# EXPORTACIONES
# =====================================================
def generar_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        data = df.copy()
        if not data.empty:
            data["fecha"] = pd.to_datetime(data["fecha"], errors="coerce").dt.strftime("%d/%m/%Y")
        data.to_excel(writer, index=False, sheet_name="Registros")

        if not df.empty:
            resumen_ubr = df.groupby("ubr", as_index=False)[["servicios", "beneficiarios"]].sum()
            resumen_serv = df.groupby("servicio", as_index=False)[["servicios", "beneficiarios"]].sum().sort_values("servicios", ascending=False)
            resumen_mes = df.groupby(["anio", "mes"], as_index=False)[["servicios", "beneficiarios"]].sum()
            resumen_ubr.to_excel(writer, index=False, sheet_name="Resumen UBR")
            resumen_serv.to_excel(writer, index=False, sheet_name="Resumen Servicio")
            resumen_mes.to_excel(writer, index=False, sheet_name="Resumen Mensual")

        wb = writer.book
        fmt_header = wb.add_format({"bold": True, "bg_color": "#0F766E", "font_color": "white", "border": 1})
        fmt_num = wb.add_format({"num_format": "#,##0"})
        for ws in writer.sheets.values():
            ws.set_row(0, None, fmt_header)
            ws.set_column(0, 20, 18)
            ws.set_column(7, 8, 14, fmt_num)
    output.seek(0)
    return output.getvalue()


def generar_pdf(df):
    if not REPORTLAB_OK:
        return None
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    styles = getSampleStyleSheet()
    elements = []
    elements.append(Paragraph("Reporte de Servicios UBR DIF Hermosillo", styles["Title"]))
    elements.append(Spacer(1, 12))
    total_serv = int(df["servicios"].sum()) if not df.empty else 0
    total_ben = int(df["beneficiarios"].sum()) if not df.empty else 0
    elements.append(Paragraph(f"Total de servicios: {total_serv:,} &nbsp;&nbsp; Total de beneficiarios: {total_ben:,}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    if df.empty:
        elements.append(Paragraph("No hay registros en el periodo seleccionado.", styles["Normal"]))
    else:
        resumen = df.groupby(["ubr", "servicio"], as_index=False)[["servicios", "beneficiarios"]].sum()
        resumen = resumen.sort_values(["ubr", "servicios"], ascending=[True, False]).head(40)
        tabla = [["UBR", "Servicio", "Servicios", "Beneficiarios"]]
        for _, r in resumen.iterrows():
            tabla.append([r["ubr"], r["servicio"], f"{int(r['servicios']):,}", f"{int(r['beneficiarios']):,}"])
        t = Table(tabla, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F766E")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

# =====================================================
# PANTALLAS
# =====================================================
def pantalla_inicio(df):
    header()
    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi("Total servicios", f"{int(df['servicios'].sum()) if not df.empty else 0:,}")
    with c2: kpi("Total beneficiarios", f"{int(df['beneficiarios'].sum()) if not df.empty else 0:,}")
    with c3: kpi("Registros", f"{len(df):,}")
    with c4:
        ratio = (df["servicios"].sum() / df["beneficiarios"].sum()) if not df.empty and df["beneficiarios"].sum() else 0
        kpi("Servicios por beneficiario", f"{ratio:.2f}")

    st.markdown("<div class='section-title'>📊 Dashboard general</div>", unsafe_allow_html=True)
    if df.empty:
        st.info("Todavía no hay registros. Entra a Captura o Importar Excel.")
        return

    col1, col2 = st.columns(2)
    resumen_ubr = df.groupby("ubr", as_index=False)[["servicios", "beneficiarios"]].sum()
    with col1:
        fig = px.bar(resumen_ubr, x="ubr", y="servicios", text="servicios", title="Servicios por UBR")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = px.bar(resumen_ubr, x="ubr", y="beneficiarios", text="beneficiarios", title="Beneficiarios por UBR")
        st.plotly_chart(fig, use_container_width=True)

    mensual = df.groupby(["anio", "mes"], as_index=False)[["servicios", "beneficiarios"]].sum()
    mensual["periodo"] = mensual["anio"].astype(str) + "-" + mensual["mes"].astype(str).str.zfill(2)
    fig = px.line(mensual, x="periodo", y=["servicios", "beneficiarios"], markers=True, title="Comparativo mensual")
    st.plotly_chart(fig, use_container_width=True)


def pantalla_captura(df):
    header()
    st.markdown("<div class='section-title'>📝 Captura de servicios</div>", unsafe_allow_html=True)
    ubrs = cargar_catalogo(CAT_UBR, "ubr", UBR_DEFAULT)
    servicios_cat = cargar_catalogo(CAT_SERVICIOS, "servicio", SERVICIOS_DEFAULT)

    with st.form("form_captura", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            fecha = st.date_input("Fecha", value=date.today())
            ubr = st.selectbox("UBR", ubrs)
        with col2:
            area = st.text_input("Área", value="Servicios UBR")
            servicio = st.selectbox("Servicio", servicios_cat)
        with col3:
            servicios = st.number_input("Cantidad de servicios", min_value=0, step=1)
            beneficiarios = st.number_input("Beneficiarios", min_value=0, step=1)
        responsable = st.text_input("Responsable")
        observaciones = st.text_area("Observaciones")
        guardar = st.form_submit_button("💾 Guardar registro")

    if guardar:
        nuevo = {
            "id": next_id(df),
            "fecha": fecha,
            "anio": fecha.year,
            "mes": fecha.month,
            "ubr": ubr,
            "area": area,
            "servicio": servicio,
            "servicios": int(servicios),
            "beneficiarios": int(beneficiarios),
            "responsable": responsable,
            "observaciones": observaciones,
            "origen": "Captura manual",
        }
        df2 = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)
        guardar_registros(df2)
        st.success("Registro guardado correctamente. Actualiza la página si no se refleja de inmediato.")
        st.rerun()


def pantalla_consultas(df):
    header()
    st.markdown("<div class='section-title'>🔎 Consultas, modificación y eliminación</div>", unsafe_allow_html=True)
    if df.empty:
        st.info("No hay registros.")
        return

    min_f = pd.to_datetime(df["fecha"]).min().date()
    max_f = pd.to_datetime(df["fecha"]).max().date()
    col1, col2, col3 = st.columns(3)
    with col1: fecha_ini = st.date_input("Desde", value=min_f, key="q_ini")
    with col2: fecha_fin = st.date_input("Hasta", value=max_f, key="q_fin")
    with col3: texto = st.text_input("Buscar servicio/responsable")

    ubrs = st.multiselect("UBR", sorted(df["ubr"].dropna().unique()), default=sorted(df["ubr"].dropna().unique()))
    f = filtrar_df(df, fecha_ini, fecha_fin, ubrs, None)
    if texto:
        t = texto.lower()
        f = f[f.apply(lambda r: t in str(r.to_dict()).lower(), axis=1)]

    st.dataframe(f.sort_values("fecha", ascending=False), use_container_width=True, height=350)

    st.download_button("📥 Descargar consulta en Excel", generar_excel(f), "consulta_ubr.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.markdown("### ✏️ Modificar o eliminar registro")
    ids = f["id"].astype(int).tolist()
    if not ids:
        st.warning("No hay registros para modificar con los filtros actuales.")
        return
    registro_id = st.selectbox("Selecciona ID", ids)
    reg = df[df["id"].astype(int) == int(registro_id)].iloc[0]

    with st.form("editar"):
        col1, col2, col3 = st.columns(3)
        with col1:
            e_fecha = st.date_input("Fecha", value=pd.to_datetime(reg["fecha"]).date(), key="e_fecha")
            e_ubr = st.text_input("UBR", value=str(reg["ubr"]))
        with col2:
            e_servicio = st.text_input("Servicio", value=str(reg["servicio"]))
            e_area = st.text_input("Área", value=str(reg["area"]))
        with col3:
            e_servicios = st.number_input("Servicios", min_value=0, value=int(reg["servicios"]), key="e_serv")
            e_beneficiarios = st.number_input("Beneficiarios", min_value=0, value=int(reg["beneficiarios"]), key="e_ben")
        e_resp = st.text_input("Responsable", value=str(reg.get("responsable", "")))
        e_obs = st.text_area("Observaciones", value=str(reg.get("observaciones", "")))
        c1, c2 = st.columns(2)
        actualizar = c1.form_submit_button("💾 Actualizar")
        eliminar = c2.form_submit_button("🗑 Eliminar")

    if actualizar:
        idx = df[df["id"].astype(int) == int(registro_id)].index[0]
        df.loc[idx, ["fecha", "anio", "mes", "ubr", "area", "servicio", "servicios", "beneficiarios", "responsable", "observaciones"]] = [
            e_fecha, e_fecha.year, e_fecha.month, e_ubr.upper(), e_area, e_servicio, int(e_servicios), int(e_beneficiarios), e_resp, e_obs
        ]
        guardar_registros(df)
        st.success("Registro actualizado.")
        st.rerun()
    if eliminar:
        df2 = df[df["id"].astype(int) != int(registro_id)]
        guardar_registros(df2)
        st.success("Registro eliminado.")
        st.rerun()


def pantalla_reportes(df):
    header()
    st.markdown("<div class='section-title'>📊 Reportes por mes, rango y UBR</div>", unsafe_allow_html=True)
    if df.empty:
        st.info("No hay información para reportar.")
        return
    min_f = pd.to_datetime(df["fecha"]).min().date()
    max_f = pd.to_datetime(df["fecha"]).max().date()

    modo = st.radio("Tipo de reporte", ["Rango de fechas", "Mes específico", "Año completo"], horizontal=True)
    if modo == "Rango de fechas":
        col1, col2 = st.columns(2)
        with col1: fecha_ini = st.date_input("Fecha inicial", value=min_f)
        with col2: fecha_fin = st.date_input("Fecha final", value=max_f)
    elif modo == "Mes específico":
        anios = sorted(df["anio"].dropna().astype(int).unique())
        col1, col2 = st.columns(2)
        with col1: anio = st.selectbox("Año", anios, index=len(anios)-1)
        with col2: mes = st.selectbox("Mes", list(MESES_NOMBRE.keys()), format_func=lambda x: MESES_NOMBRE[x])
        fecha_ini = date(int(anio), int(mes), 1)
        if mes == 12:
            fecha_fin = date(int(anio), 12, 31)
        else:
            fecha_fin = pd.Timestamp(int(anio), int(mes)+1, 1).date() - pd.Timedelta(days=1)
    else:
        anios = sorted(df["anio"].dropna().astype(int).unique())
        anio = st.selectbox("Año", anios, index=len(anios)-1)
        fecha_ini = date(int(anio), 1, 1)
        fecha_fin = date(int(anio), 12, 31)

    ubrs = st.multiselect("UBR", sorted(df["ubr"].dropna().unique()), default=sorted(df["ubr"].dropna().unique()))
    servicios = st.multiselect("Servicio", sorted(df["servicio"].dropna().unique()))
    f = filtrar_df(df, fecha_ini, fecha_fin, ubrs, servicios)

    c1, c2, c3 = st.columns(3)
    with c1: kpi("Servicios", f"{int(f['servicios'].sum()) if not f.empty else 0:,}")
    with c2: kpi("Beneficiarios", f"{int(f['beneficiarios'].sum()) if not f.empty else 0:,}")
    with c3: kpi("Registros", f"{len(f):,}")

    if f.empty:
        st.warning("No hay registros en ese periodo.")
        return

    tab1, tab2, tab3 = st.tabs(["Resumen UBR", "Resumen Servicio", "Detalle"])
    with tab1:
        resumen = f.groupby("ubr", as_index=False)[["servicios", "beneficiarios"]].sum()
        st.dataframe(resumen, use_container_width=True)
        st.plotly_chart(px.bar(resumen, x="ubr", y=["servicios", "beneficiarios"], barmode="group"), use_container_width=True)
    with tab2:
        resumen = f.groupby("servicio", as_index=False)[["servicios", "beneficiarios"]].sum().sort_values("servicios", ascending=False)
        st.dataframe(resumen, use_container_width=True)
        st.plotly_chart(px.bar(resumen.head(15), x="servicio", y="servicios", text="servicios"), use_container_width=True)
    with tab3:
        st.dataframe(f.sort_values("fecha"), use_container_width=True, height=400)

    colx, colp = st.columns(2)
    with colx:
        st.download_button("📥 Descargar Excel", generar_excel(f), "reporte_ubr.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with colp:
        pdf = generar_pdf(f)
        if pdf:
            st.download_button("📄 Descargar PDF", pdf, "reporte_ubr.pdf", mime="application/pdf")
        else:
            st.info("Para PDF instala reportlab: pip install reportlab")


def pantalla_importar(df):
    header()
    st.markdown("<div class='section-title'>📤 Importar Excel histórico</div>", unsafe_allow_html=True)
    st.markdown("""
    <div class='warning-box'>
    Este módulo importa el Excel que ya tienes. Si el archivo es concentrado, lo convierte a registros mensuales
    usando los meses encontrados en las hojas de Hermosillo, PMA y Kino.
    </div>
    """, unsafe_allow_html=True)

    anio_default = st.number_input("Año histórico por defecto", min_value=2000, max_value=2100, value=2021, step=1)
    archivo = st.file_uploader("Sube el Excel histórico", type=["xlsx", "xls"])

    if archivo:
        try:
            vista = pd.read_excel(archivo, sheet_name=0, header=None, nrows=15)
            st.write("Vista previa del archivo:")
            st.dataframe(vista, use_container_width=True)
            archivo.seek(0)
            imp = importar_excel_historico(archivo, anio_default=int(anio_default))
            st.success(f"Registros detectados para importar: {len(imp)}")
            if not imp.empty:
                st.dataframe(imp.head(100), use_container_width=True)
                if st.button("✅ Importar registros al sistema"):
                    imp = imp.copy()
                    start = next_id(df)
                    imp.insert(0, "id", range(start, start + len(imp)))
                    for col in COLUMNAS:
                        if col not in imp.columns:
                            imp[col] = "" if col not in ["servicios", "beneficiarios", "anio", "mes"] else 0
                    final = pd.concat([df, imp[COLUMNAS]], ignore_index=True)
                    guardar_registros(final)
                    st.success("Importación realizada correctamente.")
                    st.rerun()
            else:
                st.error("No se pudieron detectar registros. Revisa que las hojas tengan meses y servicios.")
        except Exception as e:
            st.error(f"Error al importar: {e}")


def pantalla_catalogos():
    header()
    st.markdown("<div class='section-title'>⚙ Catálogos</div>", unsafe_allow_html=True)
    ubrs = cargar_catalogo(CAT_UBR, "ubr", UBR_DEFAULT)
    servicios = cargar_catalogo(CAT_SERVICIOS, "servicio", SERVICIOS_DEFAULT)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("UBR")
        txt_ubr = st.text_area("Una UBR por línea", value="\n".join(ubrs), height=220)
        if st.button("Guardar UBR"):
            vals = [x.strip().upper() for x in txt_ubr.splitlines() if x.strip()]
            pd.DataFrame({"ubr": sorted(set(vals))}).to_csv(CAT_UBR, index=False)
            st.success("Catálogo UBR guardado.")
            st.rerun()
    with col2:
        st.subheader("Servicios")
        txt_serv = st.text_area("Un servicio por línea", value="\n".join(servicios), height=220)
        if st.button("Guardar servicios"):
            vals = [x.strip() for x in txt_serv.splitlines() if x.strip()]
            pd.DataFrame({"servicio": sorted(set(vals))}).to_csv(CAT_SERVICIOS, index=False)
            st.success("Catálogo de servicios guardado.")
            st.rerun()

# =====================================================
# APP PRINCIPAL
# =====================================================
def main():
    init_files()
    df = cargar_registros()

    st.sidebar.title("🏥 Sistema UBR")
    menu = st.sidebar.radio(
        "Menú principal",
        ["🏠 Inicio", "📝 Captura", "🔎 Consultas", "📊 Reportes", "📤 Importar Excel", "⚙ Catálogos"]
    )
    st.sidebar.divider()
    st.sidebar.caption("Base local: data/registros_ubr.csv")
    st.sidebar.caption("Para multiusuario permanente se recomienda Firebase.")

    if menu == "🏠 Inicio":
        pantalla_inicio(df)
    elif menu == "📝 Captura":
        pantalla_captura(df)
    elif menu == "🔎 Consultas":
        pantalla_consultas(df)
    elif menu == "📊 Reportes":
        pantalla_reportes(df)
    elif menu == "📤 Importar Excel":
        pantalla_importar(df)
    elif menu == "⚙ Catálogos":
        pantalla_catalogos()

if __name__ == "__main__":
    main()
