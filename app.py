import io
from pathlib import Path
from datetime import datetime, date

import pandas as pd
import plotly.express as px
import streamlit as st

# =====================================================
# CONFIGURACIÓN GENERAL
# =====================================================
st.set_page_config(
    page_title="Sistema UBR - Reporte Mensual",
    page_icon="🏥",
    layout="wide"
)

COLOR_PRINCIPAL = "#7A1E48"
COLOR_SECUNDARIO = "#0F766E"
COLOR_FONDO = "#F6F7FB"
ARCHIVO_DEFAULT = Path("reporte_servicios_concentrado.xlsx")

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12
}

st.markdown(f"""
<style>
    .stApp {{ background-color: {COLOR_FONDO}; }}
    .block-container {{ padding-top: 1.2rem; padding-bottom: 2rem; }}
    .titulo {{
        background: linear-gradient(90deg, {COLOR_PRINCIPAL}, {COLOR_SECUNDARIO});
        color: white;
        padding: 28px;
        border-radius: 18px;
        text-align: center;
        margin-bottom: 22px;
        box-shadow: 0 4px 15px rgba(0,0,0,.12);
    }}
    .titulo h1 {{ margin-bottom: 5px; font-size: 42px; }}
    .titulo p {{ font-size: 17px; margin: 0; }}
    .card {{
        background: white;
        border-radius: 15px;
        padding: 18px;
        box-shadow: 0 2px 12px rgba(0,0,0,.07);
        border-left: 7px solid {COLOR_PRINCIPAL};
        margin-bottom: 12px;
    }}
    div[data-testid="stMetricValue"] {{ font-size: 34px; }}
</style>
""", unsafe_allow_html=True)

# =====================================================
# FUNCIONES
# =====================================================
def limpiar_numero(valor):
    if pd.isna(valor):
        return 0
    if isinstance(valor, str):
        valor = valor.replace(",", "").replace(" ", "").strip()
        if valor == "":
            return 0
    try:
        return int(float(valor))
    except Exception:
        return 0


def limpiar_texto(valor):
    if pd.isna(valor):
        return ""
    return str(valor).strip()


def nombre_ubr(nombre_hoja):
    n = str(nombre_hoja).lower()
    if "hermosillo" in n:
        return "HERMOSILLO"
    if "pma" in n or "miguel" in n:
        return "PMA"
    if "kino" in n:
        return "KINO"
    return str(nombre_hoja).upper()


@st.cache_data(show_spinner=False)
def cargar_excel(archivo):
    xls = pd.ExcelFile(archivo)
    hojas = {nombre: pd.read_excel(archivo, sheet_name=nombre, header=None) for nombre in xls.sheet_names}
    return hojas


def parsear_mensual(hojas):
    """
    Convierte las hojas mensuales a formato largo:
    UBR, Año, Mes, Periodo, Servicio, Servicios, Beneficiarios.
    Detecta encabezados tipo: Area 2021, septiembre, octubre...
    """
    registros = []

    for hoja, df in hojas.items():
        if str(hoja).upper() == "CONCENTRADO":
            continue

        ubr = nombre_ubr(hoja)
        filas, cols = df.shape

        for i in range(filas):
            texto_area = limpiar_texto(df.iat[i, 1] if cols > 1 else "").lower()
            if not texto_area.startswith("area"):
                continue

            # Detectar año en "Area 2021"
            anio = None
            for parte in texto_area.replace("á", "a").split():
                if parte.isdigit() and len(parte) == 4:
                    anio = int(parte)
                    break
            if anio is None:
                continue

            # Detectar columnas de meses. Normalmente servicio en col 2 y beneficiarios en col 3.
            columnas_mes = []
            c = 2
            while c < cols:
                mes_txt = limpiar_texto(df.iat[i, c]).lower()
                mes_txt = mes_txt.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
                if mes_txt in MESES:
                    columnas_mes.append((mes_txt, c, c + 1))
                    c += 2
                else:
                    c += 1

            if not columnas_mes:
                continue

            # Los servicios empiezan dos filas después del encabezado y terminan antes del siguiente Area
            j = i + 2
            while j < filas:
                posible_siguiente = limpiar_texto(df.iat[j, 1] if cols > 1 else "").lower()
                if posible_siguiente.startswith("area"):
                    break

                servicio = limpiar_texto(df.iat[j, 1] if cols > 1 else "")
                servicio_limpio = servicio.upper().strip()

                if servicio and servicio_limpio not in ["TOTAL", "TOTALES"]:
                    for mes_txt, col_serv, col_ben in columnas_mes:
                        servicios = limpiar_numero(df.iat[j, col_serv] if col_serv < cols else 0)
                        beneficiarios = limpiar_numero(df.iat[j, col_ben] if col_ben < cols else 0)
                        if servicios != 0 or beneficiarios != 0:
                            mes_num = MESES[mes_txt]
                            registros.append({
                                "UBR": ubr,
                                "Año": anio,
                                "Mes": mes_txt.capitalize(),
                                "MesNum": mes_num,
                                "Periodo": pd.Timestamp(year=anio, month=mes_num, day=1),
                                "Servicio": servicio,
                                "Servicios": servicios,
                                "Beneficiarios": beneficiarios,
                            })
                j += 1

    data = pd.DataFrame(registros)
    if not data.empty:
        data = data.sort_values(["Periodo", "UBR", "Servicio"]).reset_index(drop=True)
    return data


def generar_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        detalle = df.copy()
        if "Periodo" in detalle.columns:
            detalle["Periodo"] = pd.to_datetime(detalle["Periodo"]).dt.strftime("%d/%m/%Y")
        detalle.to_excel(writer, index=False, sheet_name="Detalle")

        resumen_ubr = df.groupby("UBR", as_index=False)[["Servicios", "Beneficiarios"]].sum()
        resumen_ubr.to_excel(writer, index=False, sheet_name="Resumen por UBR")

        resumen_mes = df.groupby(["Año", "MesNum", "Mes"], as_index=False)[["Servicios", "Beneficiarios"]].sum()
        resumen_mes = resumen_mes.sort_values(["Año", "MesNum"]).drop(columns=["MesNum"])
        resumen_mes.to_excel(writer, index=False, sheet_name="Resumen por Mes")

        resumen_servicio = df.groupby("Servicio", as_index=False)[["Servicios", "Beneficiarios"]].sum()
        resumen_servicio = resumen_servicio.sort_values("Servicios", ascending=False)
        resumen_servicio.to_excel(writer, index=False, sheet_name="Resumen Servicio")

    output.seek(0)
    return output


def mostrar_kpis(df):
    servicios_total = int(df["Servicios"].sum()) if not df.empty else 0
    beneficiarios_total = int(df["Beneficiarios"].sum()) if not df.empty else 0
    registros_total = len(df)
    promedio = servicios_total / beneficiarios_total if beneficiarios_total else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total de servicios", f"{servicios_total:,}")
    c2.metric("Total de beneficiarios", f"{beneficiarios_total:,}")
    c3.metric("Registros", f"{registros_total:,}")
    c4.metric("Servicios por beneficiario", f"{promedio:,.2f}")


def grafica_barras(df, x, y, titulo):
    fig = px.bar(df, x=x, y=y, text=y, title=titulo)
    fig.update_traces(texttemplate="%{text:,}", textposition="outside")
    fig.update_layout(title_x=0.02, height=430)
    st.plotly_chart(fig, use_container_width=True)

# =====================================================
# ENCABEZADO
# =====================================================
st.markdown("""
<div class='titulo'>
    <h1>🏥 Sistema de Reporte de Servicios UBR</h1>
    <p>Reportes por mes, rango de fechas, UBR, servicio y beneficiarios</p>
</div>
""", unsafe_allow_html=True)

# =====================================================
# CARGA DE ARCHIVO
# =====================================================
st.sidebar.title("🏥 Sistema UBR")
st.sidebar.caption("DIF Hermosillo / Unidad Básica de Rehabilitación")

archivo_subido = st.sidebar.file_uploader("Subir archivo Excel", type=["xlsx", "xls"])
archivo = archivo_subido if archivo_subido else (ARCHIVO_DEFAULT if ARCHIVO_DEFAULT.exists() else None)

if archivo is None:
    st.info("Sube el archivo Excel para iniciar el sistema.")
    st.stop()

try:
    hojas = cargar_excel(archivo)
except Exception as e:
    st.error(f"No se pudo leer el archivo: {e}")
    st.stop()

base = parsear_mensual(hojas)

if base.empty:
    st.error("No se encontraron datos mensuales. Revisa que las hojas tengan columnas por mes.")
    st.stop()

st.sidebar.success("Archivo cargado correctamente")
with st.sidebar.expander("📄 Hojas detectadas", expanded=False):
    for i, h in enumerate(hojas.keys(), start=1):
        st.write(f"{i}. {h}")

# =====================================================
# MENÚ Y FILTROS
# =====================================================
menu = st.sidebar.radio(
    "Menú principal",
    ["📊 Dashboard", "🔍 Consultas", "📑 Reportes", "📆 Comparativo mensual", "📁 Hojas originales"],
    index=0
)

st.sidebar.header("Filtros")

fecha_min = base["Periodo"].min().date()
fecha_max = base["Periodo"].max().date()

opcion_periodo = st.sidebar.selectbox(
    "Periodo rápido",
    ["Todo", "Este año", "Seleccionar rango"],
    index=0
)

if opcion_periodo == "Todo":
    rango = (fecha_min, fecha_max)
elif opcion_periodo == "Este año":
    anio_max = fecha_max.year
    rango = (date(anio_max, 1, 1), date(anio_max, 12, 31))
else:
    rango = st.sidebar.date_input(
        "Rango de fechas",
        value=(fecha_min, fecha_max),
        min_value=fecha_min,
        max_value=fecha_max,
        format="DD/MM/YYYY"
    )
    if isinstance(rango, tuple) and len(rango) == 2:
        rango = rango
    else:
        rango = (fecha_min, fecha_max)

fecha_inicio, fecha_fin = rango

ubrs = sorted(base["UBR"].dropna().unique().tolist())
servicios = sorted(base["Servicio"].dropna().unique().tolist())
anios = sorted(base["Año"].dropna().unique().tolist())

filtro_ubr = st.sidebar.multiselect("UBR", ubrs, default=ubrs)
filtro_servicio = st.sidebar.multiselect("Servicio", servicios, default=servicios)
filtro_anio = st.sidebar.multiselect("Año", anios, default=anios)

filtrado = base[
    (base["Periodo"].dt.date >= fecha_inicio) &
    (base["Periodo"].dt.date <= fecha_fin) &
    (base["UBR"].isin(filtro_ubr)) &
    (base["Servicio"].isin(filtro_servicio)) &
    (base["Año"].isin(filtro_anio))
].copy()

st.sidebar.info(f"Periodo: {fecha_inicio.strftime('%d/%m/%Y')} al {fecha_fin.strftime('%d/%m/%Y')}")

# =====================================================
# DASHBOARD
# =====================================================
if menu == "📊 Dashboard":
    st.subheader("📊 Dashboard general")
    mostrar_kpis(filtrado)
    st.divider()

    if filtrado.empty:
        st.warning("No hay datos con los filtros seleccionados.")
        st.stop()

    resumen_ubr = filtrado.groupby("UBR", as_index=False)[["Servicios", "Beneficiarios"]].sum()
    col1, col2 = st.columns(2)
    with col1:
        grafica_barras(resumen_ubr, "UBR", "Servicios", "Servicios por UBR")
    with col2:
        grafica_barras(resumen_ubr, "UBR", "Beneficiarios", "Beneficiarios por UBR")

    st.subheader("🏆 Servicios con mayor cantidad")
    top_servicios = filtrado.groupby("Servicio", as_index=False)[["Servicios", "Beneficiarios"]].sum()
    top_servicios = top_servicios.sort_values("Servicios", ascending=False).head(15)
    fig = px.bar(top_servicios, x="Servicios", y="Servicio", orientation="h", text="Servicios", title="Top 15 servicios")
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=600)
    fig.update_traces(texttemplate="%{text:,}", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

# =====================================================
# CONSULTAS
# =====================================================
elif menu == "🔍 Consultas":
    st.subheader("🔍 Consulta de información")
    buscar = st.text_input("Buscar servicio", placeholder="Ejemplo: terapia, consulta, cámara, neuropsicología...")
    consulta = filtrado.copy()
    if buscar.strip():
        consulta = consulta[consulta["Servicio"].str.contains(buscar, case=False, na=False)]

    mostrar_kpis(consulta)
    st.dataframe(consulta.drop(columns=["MesNum"]), use_container_width=True, hide_index=True)

    excel_generado = generar_excel(consulta)
    st.download_button(
        "⬇️ Descargar consulta en Excel",
        data=excel_generado,
        file_name=f"consulta_ubr_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

# =====================================================
# REPORTES
# =====================================================
elif menu == "📑 Reportes":
    st.subheader("📑 Reportes por periodo")
    st.success(f"Reporte del {fecha_inicio.strftime('%d/%m/%Y')} al {fecha_fin.strftime('%d/%m/%Y')}")
    mostrar_kpis(filtrado)
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Resumen por UBR")
        resumen_ubr = filtrado.groupby("UBR", as_index=False)[["Servicios", "Beneficiarios"]].sum()
        st.dataframe(resumen_ubr, use_container_width=True, hide_index=True)
    with col2:
        st.markdown("### Resumen por mes")
        resumen_mes = filtrado.groupby(["Año", "MesNum", "Mes"], as_index=False)[["Servicios", "Beneficiarios"]].sum()
        resumen_mes = resumen_mes.sort_values(["Año", "MesNum"]).drop(columns=["MesNum"])
        st.dataframe(resumen_mes, use_container_width=True, hide_index=True)

    st.markdown("### Resumen por servicio")
    resumen_servicio = filtrado.groupby("Servicio", as_index=False)[["Servicios", "Beneficiarios"]].sum()
    resumen_servicio = resumen_servicio.sort_values("Servicios", ascending=False)
    st.dataframe(resumen_servicio, use_container_width=True, hide_index=True)

    excel_generado = generar_excel(filtrado)
    st.download_button(
        "⬇️ Descargar reporte en Excel",
        data=excel_generado,
        file_name=f"reporte_ubr_{fecha_inicio.strftime('%Y%m%d')}_al_{fecha_fin.strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

    st.info("Para sacar 1 mes: selecciona del día 01 al último día del mes. Para 2 meses: selecciona el rango completo.")

# =====================================================
# COMPARATIVO MENSUAL
# =====================================================
elif menu == "📆 Comparativo mensual":
    st.subheader("📆 Comparativo mensual")
    mostrar_kpis(filtrado)

    if filtrado.empty:
        st.warning("No hay datos con los filtros seleccionados.")
        st.stop()

    mensual = filtrado.groupby(["Año", "MesNum", "Mes"], as_index=False)[["Servicios", "Beneficiarios"]].sum()
    mensual = mensual.sort_values(["Año", "MesNum"])
    mensual["Periodo texto"] = mensual["Mes"] + " " + mensual["Año"].astype(str)

    fig1 = px.line(mensual, x="Periodo texto", y="Servicios", markers=True, title="Servicios por mes")
    fig1.update_layout(height=430)
    st.plotly_chart(fig1, use_container_width=True)

    fig2 = px.line(mensual, x="Periodo texto", y="Beneficiarios", markers=True, title="Beneficiarios por mes")
    fig2.update_layout(height=430)
    st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(mensual.drop(columns=["MesNum"]), use_container_width=True, hide_index=True)

# =====================================================
# HOJAS ORIGINALES
# =====================================================
elif menu == "📁 Hojas originales":
    st.subheader("📁 Hojas originales del archivo")
    hoja_sel = st.selectbox("Selecciona una hoja", list(hojas.keys()))
    st.dataframe(hojas[hoja_sel], use_container_width=True)

st.caption("Sistema UBR desarrollado en Python + Streamlit")
