import sqlite3
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from fpdf import FPDF

DB_PATH = Path("ubr_servicios.db")

st.set_page_config(
    page_title="Sistema UBR DIF Hermosillo",
    page_icon="🏥",
    layout="wide",
)

# =========================
# ESTILO
# =========================
st.markdown("""
<style>
.main { background-color: #f5f7fb; }
.block-container { padding-top: 1.5rem; }
.card {
    padding: 18px;
    border-radius: 16px;
    background: white;
    box-shadow: 0 2px 10px rgba(0,0,0,.08);
    text-align: center;
}
.card h2 { margin: 0; color: #0f4c81; font-size: 32px; }
.card p { margin: 0; color: #555; font-weight: 600; }
.titulo {
    background: linear-gradient(90deg,#0f4c81,#1f7a8c);
    padding: 20px;
    border-radius: 18px;
    color:white;
    margin-bottom:20px;
}
</style>
""", unsafe_allow_html=True)

# =========================
# BASE DE DATOS
# =========================
def conectar():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def crear_tablas():
    con = conectar()
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS servicios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            ubr TEXT NOT NULL,
            area TEXT,
            servicio TEXT NOT NULL,
            beneficiarios INTEGER DEFAULT 0,
            cantidad_servicios INTEGER DEFAULT 0,
            responsable TEXT,
            observaciones TEXT,
            creado_en TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.commit()
    con.close()


def insertar_registro(fecha, ubr, area, servicio, beneficiarios, cantidad_servicios, responsable, observaciones):
    con = conectar()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO servicios
        (fecha, ubr, area, servicio, beneficiarios, cantidad_servicios, responsable, observaciones)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (str(fecha), ubr, area, servicio, int(beneficiarios), int(cantidad_servicios), responsable, observaciones))
    con.commit()
    con.close()


def actualizar_registro(id_registro, fecha, ubr, area, servicio, beneficiarios, cantidad_servicios, responsable, observaciones):
    con = conectar()
    cur = con.cursor()
    cur.execute("""
        UPDATE servicios
        SET fecha=?, ubr=?, area=?, servicio=?, beneficiarios=?, cantidad_servicios=?, responsable=?, observaciones=?
        WHERE id=?
    """, (str(fecha), ubr, area, servicio, int(beneficiarios), int(cantidad_servicios), responsable, observaciones, int(id_registro)))
    con.commit()
    con.close()


def eliminar_registro(id_registro):
    con = conectar()
    cur = con.cursor()
    cur.execute("DELETE FROM servicios WHERE id=?", (int(id_registro),))
    con.commit()
    con.close()


def cargar_datos():
    con = conectar()
    df = pd.read_sql_query("SELECT * FROM servicios ORDER BY fecha DESC, id DESC", con)
    con.close()
    if not df.empty:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        df["mes"] = df["fecha"].dt.strftime("%Y-%m")
        df["año"] = df["fecha"].dt.year
    return df

crear_tablas()

UBRS = ["Hermosillo", "Poblado Miguel Alemán", "Bahía de Kino"]
AREAS = ["Terapia Física", "Lenguaje", "Psicología", "Trabajo Social", "Consulta", "Otro"]
SERVICIOS = [
    "Terapia física", "Terapia de lenguaje", "Consulta médica", "Psicología",
    "Trabajo social", "Entrega de apoyo", "Valoración", "Otro"
]

# =========================
# FUNCIONES REPORTE
# =========================
def filtrar_df(df, fecha_ini, fecha_fin, ubr, servicio):
    if df.empty:
        return df
    f = df.copy()
    f = f[(f["fecha"].dt.date >= fecha_ini) & (f["fecha"].dt.date <= fecha_fin)]
    if ubr != "Todas":
        f = f[f["ubr"] == ubr]
    if servicio != "Todos":
        f = f[f["servicio"] == servicio]
    return f


def excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Registros", index=False)
        if not df.empty:
            resumen_ubr = df.groupby("ubr", as_index=False)[["cantidad_servicios", "beneficiarios"]].sum()
            resumen_serv = df.groupby("servicio", as_index=False)[["cantidad_servicios", "beneficiarios"]].sum()
            resumen_mes = df.groupby("mes", as_index=False)[["cantidad_servicios", "beneficiarios"]].sum()
            resumen_ubr.to_excel(writer, sheet_name="Resumen UBR", index=False)
            resumen_serv.to_excel(writer, sheet_name="Resumen Servicio", index=False)
            resumen_mes.to_excel(writer, sheet_name="Resumen Mensual", index=False)
    return output.getvalue()


def pdf_bytes(df, titulo="Reporte UBR"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, titulo, ln=True, align="C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 8, f"Fecha de generación: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
    pdf.ln(4)

    total_serv = int(df["cantidad_servicios"].sum()) if not df.empty else 0
    total_ben = int(df["beneficiarios"].sum()) if not df.empty else 0
    pdf.cell(0, 8, f"Total de servicios: {total_serv}", ln=True)
    pdf.cell(0, 8, f"Total de beneficiarios: {total_ben}", ln=True)
    pdf.ln(4)

    pdf.set_font("Arial", "B", 9)
    pdf.cell(28, 8, "Fecha", border=1)
    pdf.cell(38, 8, "UBR", border=1)
    pdf.cell(50, 8, "Servicio", border=1)
    pdf.cell(25, 8, "Servicios", border=1)
    pdf.cell(30, 8, "Beneficiarios", border=1, ln=True)

    pdf.set_font("Arial", "", 8)
    for _, r in df.head(35).iterrows():
        pdf.cell(28, 7, str(r["fecha"].date()), border=1)
        pdf.cell(38, 7, str(r["ubr"])[:20], border=1)
        pdf.cell(50, 7, str(r["servicio"])[:27], border=1)
        pdf.cell(25, 7, str(int(r["cantidad_servicios"])), border=1)
        pdf.cell(30, 7, str(int(r["beneficiarios"])), border=1, ln=True)

    if len(df) > 35:
        pdf.ln(4)
        pdf.cell(0, 8, f"Nota: PDF muestra 35 registros. Para ver todo, descargue Excel.", ln=True)

    return bytes(pdf.output(dest="S"))

# =========================
# MENÚ
# =========================
st.sidebar.title("🏥 Sistema UBR")
menu = st.sidebar.radio(
    "Menú principal",
    ["🏠 Inicio", "📝 Captura", "🔎 Consultas", "📊 Reportes", "📥 Importar Excel", "⚙️ Catálogos"]
)

st.markdown("""
<div class='titulo'>
<h1>🏥 Sistema Integral de Servicios UBR DIF Hermosillo</h1>
<p>Captura, consulta y reportes por mes, UBR y servicio</p>
</div>
""", unsafe_allow_html=True)

# =========================
# INICIO
# =========================
df = cargar_datos()

if menu == "🏠 Inicio":
    total_servicios = int(df["cantidad_servicios"].sum()) if not df.empty else 0
    total_beneficiarios = int(df["beneficiarios"].sum()) if not df.empty else 0
    total_registros = len(df)

    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='card'><h2>{total_servicios:,}</h2><p>Total de servicios</p></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='card'><h2>{total_beneficiarios:,}</h2><p>Total de beneficiarios</p></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='card'><h2>{total_registros:,}</h2><p>Registros capturados</p></div>", unsafe_allow_html=True)

    st.subheader("📈 Estadísticas generales")
    if df.empty:
        st.info("Aún no hay registros capturados. Entra a 📝 Captura para iniciar.")
    else:
        col1, col2 = st.columns(2)
        resumen_ubr = df.groupby("ubr", as_index=False)[["cantidad_servicios", "beneficiarios"]].sum()
        resumen_mes = df.groupby("mes", as_index=False)[["cantidad_servicios", "beneficiarios"]].sum()
        with col1:
            st.plotly_chart(px.bar(resumen_ubr, x="ubr", y="cantidad_servicios", title="Servicios por UBR"), use_container_width=True)
        with col2:
            st.plotly_chart(px.line(resumen_mes, x="mes", y="cantidad_servicios", markers=True, title="Servicios por mes"), use_container_width=True)

# =========================
# CAPTURA
# =========================
elif menu == "📝 Captura":
    st.subheader("📝 Captura de servicios")
    with st.form("form_captura", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        fecha = c1.date_input("Fecha del servicio", value=date.today())
        ubr = c2.selectbox("UBR", UBRS)
        area = c3.selectbox("Área", AREAS)

        c4, c5, c6 = st.columns(3)
        servicio = c4.selectbox("Servicio", SERVICIOS)
        cantidad_servicios = c5.number_input("Cantidad de servicios", min_value=0, step=1)
        beneficiarios = c6.number_input("Beneficiarios", min_value=0, step=1)

        responsable = st.text_input("Responsable")
        observaciones = st.text_area("Observaciones")

        guardar = st.form_submit_button("💾 Guardar captura")
        if guardar:
            insertar_registro(fecha, ubr, area, servicio, beneficiarios, cantidad_servicios, responsable, observaciones)
            st.success("Registro guardado correctamente.")
            st.rerun()

# =========================
# CONSULTAS / EDITAR / ELIMINAR
# =========================
elif menu == "🔎 Consultas":
    st.subheader("🔎 Consulta, modificación y eliminación")
    if df.empty:
        st.info("No hay registros capturados.")
    else:
        texto = st.text_input("Buscar por UBR, servicio, área, responsable u observaciones")
        vista = df.copy()
        if texto:
            t = texto.lower()
            vista = vista[
                vista.astype(str).apply(lambda row: row.str.lower().str.contains(t, na=False).any(), axis=1)
            ]
        st.dataframe(vista, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("✏️ Modificar o eliminar registro")
        id_sel = st.selectbox("Selecciona ID", vista["id"].tolist())
        reg = df[df["id"] == id_sel].iloc[0]

        with st.form("form_editar"):
            c1, c2, c3 = st.columns(3)
            fecha_e = c1.date_input("Fecha", value=reg["fecha"].date())
            ubr_e = c2.selectbox("UBR", UBRS, index=UBRS.index(reg["ubr"]) if reg["ubr"] in UBRS else 0)
            area_e = c3.selectbox("Área", AREAS, index=AREAS.index(reg["area"]) if reg["area"] in AREAS else 0)

            c4, c5, c6 = st.columns(3)
            servicio_e = c4.selectbox("Servicio", SERVICIOS, index=SERVICIOS.index(reg["servicio"]) if reg["servicio"] in SERVICIOS else 0)
            cant_e = c5.number_input("Cantidad de servicios", min_value=0, step=1, value=int(reg["cantidad_servicios"]))
            ben_e = c6.number_input("Beneficiarios", min_value=0, step=1, value=int(reg["beneficiarios"]))
            resp_e = st.text_input("Responsable", value=str(reg["responsable"] or ""))
            obs_e = st.text_area("Observaciones", value=str(reg["observaciones"] or ""))

            colg, cole = st.columns(2)
            btn_actualizar = colg.form_submit_button("💾 Actualizar")
            btn_eliminar = cole.form_submit_button("🗑 Eliminar")

            if btn_actualizar:
                actualizar_registro(id_sel, fecha_e, ubr_e, area_e, servicio_e, ben_e, cant_e, resp_e, obs_e)
                st.success("Registro actualizado.")
                st.rerun()
            if btn_eliminar:
                eliminar_registro(id_sel)
                st.warning("Registro eliminado.")
                st.rerun()

# =========================
# REPORTES
# =========================
elif menu == "📊 Reportes":
    st.subheader("📊 Reportes por mes o rango de fechas")
    if df.empty:
        st.info("No hay registros capturados.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        fecha_ini = c1.date_input("Fecha inicial", value=df["fecha"].min().date())
        fecha_fin = c2.date_input("Fecha final", value=df["fecha"].max().date())
        ubr_f = c3.selectbox("UBR", ["Todas"] + sorted(df["ubr"].dropna().unique().tolist()))
        serv_f = c4.selectbox("Servicio", ["Todos"] + sorted(df["servicio"].dropna().unique().tolist()))

        filtrado = filtrar_df(df, fecha_ini, fecha_fin, ubr_f, serv_f)
        st.write(f"Registros encontrados: **{len(filtrado)}**")

        c1, c2 = st.columns(2)
        c1.metric("Servicios", int(filtrado["cantidad_servicios"].sum()) if not filtrado.empty else 0)
        c2.metric("Beneficiarios", int(filtrado["beneficiarios"].sum()) if not filtrado.empty else 0)

        if not filtrado.empty:
            resumen_mes = filtrado.groupby("mes", as_index=False)[["cantidad_servicios", "beneficiarios"]].sum()
            resumen_ubr = filtrado.groupby("ubr", as_index=False)[["cantidad_servicios", "beneficiarios"]].sum()
            resumen_serv = filtrado.groupby("servicio", as_index=False)[["cantidad_servicios", "beneficiarios"]].sum()

            st.plotly_chart(px.bar(resumen_mes, x="mes", y="cantidad_servicios", title="Servicios por mes"), use_container_width=True)
            st.plotly_chart(px.bar(resumen_ubr, x="ubr", y="cantidad_servicios", title="Servicios por UBR"), use_container_width=True)
            st.plotly_chart(px.bar(resumen_serv, x="servicio", y="cantidad_servicios", title="Servicios por servicio"), use_container_width=True)

            st.dataframe(filtrado, use_container_width=True, hide_index=True)

            colx, colp = st.columns(2)
            colx.download_button(
                "📥 Descargar reporte Excel",
                data=excel_bytes(filtrado),
                file_name="reporte_ubr.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            colp.download_button(
                "📄 Descargar reporte PDF",
                data=pdf_bytes(filtrado, "Reporte de Servicios UBR"),
                file_name="reporte_ubr.pdf",
                mime="application/pdf"
            )

# =========================
# IMPORTAR EXCEL
# =========================
elif menu == "📥 Importar Excel":
    st.subheader("📥 Importar registros desde Excel")
    st.info("El Excel debe traer columnas: fecha, ubr, area, servicio, beneficiarios, cantidad_servicios, responsable, observaciones.")
    archivo = st.file_uploader("Selecciona Excel", type=["xlsx", "xls"])
    if archivo:
        try:
            imp = pd.read_excel(archivo)
            st.dataframe(imp.head(20), use_container_width=True)
            if st.button("Importar registros"):
                imp.columns = [str(c).strip().lower() for c in imp.columns]
                requeridas = ["fecha", "ubr", "servicio"]
                faltan = [c for c in requeridas if c not in imp.columns]
                if faltan:
                    st.error(f"Faltan columnas obligatorias: {faltan}")
                else:
                    for _, r in imp.iterrows():
                        insertar_registro(
                            pd.to_datetime(r.get("fecha", date.today())).date(),
                            r.get("ubr", ""),
                            r.get("area", ""),
                            r.get("servicio", ""),
                            int(r.get("beneficiarios", 0) or 0),
                            int(r.get("cantidad_servicios", 0) or 0),
                            r.get("responsable", ""),
                            r.get("observaciones", ""),
                        )
                    st.success("Registros importados correctamente.")
                    st.rerun()
        except Exception as e:
            st.error(f"No se pudo importar: {e}")

# =========================
# CATALOGOS
# =========================
elif menu == "⚙️ Catálogos":
    st.subheader("⚙️ Catálogos base")
    st.write("UBR disponibles:")
    st.table(pd.DataFrame({"UBR": UBRS}))
    st.write("Servicios base:")
    st.table(pd.DataFrame({"Servicio": SERVICIOS}))
    st.warning("En esta primera versión los catálogos están dentro del código. Después podemos hacer que se editen desde pantalla.")
