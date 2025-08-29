import streamlit as st
import pandas as pd
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA Y GOOGLE SHEETS ---

st.set_page_config(
    page_title="Inventario Universal del Llano",
    page_icon="📦",
    layout="wide"
)

# Función para conectar con Google Sheets
# Se utiliza el manejo de cache para no reconectar en cada interacción.
@st.cache_resource
def connect_to_google_sheets():
    """Conecta con la API de Google Sheets usando las credenciales de Streamlit Secrets."""
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        # Carga las credenciales desde los secretos de Streamlit
        # Asegúrate de que la clave "gcp_service_account" exista en tus secretos
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        st.error("Asegúrate de haber configurado correctamente las credenciales en Streamlit Secrets. Consulta el archivo README.md.")
        return None

# Función para abrir la hoja de cálculo y las hojas de trabajo
def get_sheets(client):
    """Abre la hoja de cálculo y las hojas de trabajo necesarias."""
    try:
        # Abre la hoja de cálculo usando la URL guardada en los secretos de Streamlit
        sheet_url = st.secrets["google_sheet_url"]
        spreadsheet = client.open_by_url(sheet_url)
        
        # Define los nombres de las hojas que usará la app
        sheet_names = ["Productos", "Ventas", "Compras"]
        worksheets = {}
        
        # Verifica si cada hoja existe, si no, la crea
        for name in sheet_names:
            try:
                worksheets[name] = spreadsheet.worksheet(name)
            except gspread.WorksheetNotFound:
                worksheets[name] = spreadsheet.add_worksheet(title=name, rows="100", cols="20")
                # Si la hoja es nueva, se añaden los encabezados
                if name == "Productos":
                    worksheets[name].append_row(["ID_Producto", "Nombre", "Categoría", "Presentación", "Stock"])
                elif name == "Ventas":
                    worksheets[name].append_row(["Fecha", "ID_Producto", "Nombre", "Cantidad", "Presentación"])
                elif name == "Compras":
                    worksheets[name].append_row(["Fecha", "ID_Producto", "Nombre", "Cantidad", "Presentación"])
        
        return worksheets
    except Exception as e:
        st.error(f"Error al abrir la hoja de cálculo: {e}")
        st.error("Verifica que la URL en Streamlit Secrets sea correcta y que hayas compartido la hoja con el email de la cuenta de servicio.")
        return None

# --- CARGA DE DATOS ---

def load_data(worksheets, sheet_name):
    """Carga los datos de una hoja de trabajo específica en un DataFrame de Pandas."""
    try:
        sheet = worksheets[sheet_name]
        # set_get_dataframe_defaults para evitar problemas con celdas vacías
        df = get_as_dataframe(sheet, evaluate_formulas=True).dropna(how='all')
        return df
    except Exception as e:
        st.warning(f"No se pudieron cargar los datos de la hoja '{sheet_name}'. Puede que esté vacía. Error: {e}")
        return pd.DataFrame()


# --- APLICACIÓN PRINCIPAL ---

# Título principal de la aplicación
st.title("📦 Control de Inventario - Distribuidora Universal del Llano")
st.markdown("---")

# Conexión y carga de hojas
client = connect_to_google_sheets()

if client:
    worksheets = get_sheets(client)
    if worksheets:
        # Menú de navegación en la barra lateral
        st.sidebar.header("Menú de Navegación")
        opcion = st.sidebar.radio(
            "Selecciona una ventana:",
            ["Dashboard", "Registro de Productos", "Registro de Ventas", "Registro de Compras"]
        )

        # --- PÁGINA 1: REGISTRO DE PRODUCTOS ---
        if opcion == "Registro de Productos":
            st.header("📝 Registro de Nuevos Productos")

            df_productos = load_data(worksheets, "Productos")

            with st.form("form_nuevo_producto", clear_on_submit=True):
                st.subheader("Ingresa los datos del nuevo producto:")
                
                # Columnas para organizar el formulario
                col1, col2 = st.columns(2)
                with col1:
                    id_producto = st.text_input("Identificador del Producto (ID)")
                    nombre_producto = st.text_input("Nombre del Producto")
                    stock_inicial = st.number_input("Stock Inicial", min_value=0, step=1)
                with col2:
                    categoria = st.text_input("Categoría")
                    presentacion = st.text_input("Presentación (Ej: Caja, Unidad, Litro)")

                submitted = st.form_submit_button("Añadir Producto")

                if submitted:
                    if not all([id_producto, nombre_producto, categoria, presentacion]):
                        st.warning("Todos los campos son obligatorios.")
                    elif id_producto in df_productos["ID_Producto"].astype(str).values:
                        st.error(f"El ID '{id_producto}' ya existe. Por favor, utiliza un identificador único.")
                    else:
                        # Crear una nueva fila como DataFrame
                        nuevo_producto = pd.DataFrame([[id_producto, nombre_producto, categoria, presentacion, stock_inicial]], 
                                                      columns=["ID_Producto", "Nombre", "Categoría", "Presentación", "Stock"])
                        
                        # Añadir la nueva fila al DataFrame existente
                        df_actualizado = pd.concat([df_productos, nuevo_producto], ignore_index=True)
                        
                        # Guardar el DataFrame actualizado en Google Sheets
                        set_with_dataframe(worksheets["Productos"], df_actualizado)
                        st.success(f"¡Producto '{nombre_producto}' añadido con éxito!")

            st.markdown("---")
            st.subheader("Inventario Actual de Productos")
            df_productos_display = load_data(worksheets, "Productos")
            if not df_productos_display.empty:
                st.dataframe(df_productos_display, use_container_width=True)
            else:
                st.info("Aún no se han registrado productos.")

        # --- PÁGINA 2: REGISTRO DE VENTAS ---
        elif opcion == "Registro de Ventas":
            st.header("💸 Registro de Ventas")
            df_productos = load_data(worksheets, "Productos")

            if not df_productos.empty:
                lista_productos = df_productos["Nombre"].tolist()
                producto_seleccionado = st.selectbox("Selecciona un producto:", lista_productos)
                
                producto_info = df_productos[df_productos["Nombre"] == producto_seleccionado].iloc[0]
                
                with st.form("form_venta", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        cantidad_vendida = st.number_input("Cantidad Vendida", min_value=1, step=1)
                    with col2:
                        st.write(f"**Presentación:** {producto_info['Presentación']}")
                        st.write(f"**Stock Actual:** {producto_info['Stock']}")

                    submit_venta = st.form_submit_button("Registrar Venta")
                    
                    if submit_venta:
                        stock_actual = int(producto_info["Stock"])
                        if cantidad_vendida > stock_actual:
                            st.error(f"No hay suficiente stock. Solo quedan {stock_actual} unidades.")
                        else:
                            # Registrar la venta en la hoja "Ventas"
                            fecha_venta = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            nueva_venta = pd.DataFrame([[fecha_venta, producto_info['ID_Producto'], producto_info['Nombre'], cantidad_vendida, producto_info['Presentación']]],
                                                       columns=["Fecha", "ID_Producto", "Nombre", "Cantidad", "Presentación"])
                            
                            df_ventas_actual = load_data(worksheets, "Ventas")
                            df_ventas_final = pd.concat([df_ventas_actual, nueva_venta], ignore_index=True)
                            set_with_dataframe(worksheets["Ventas"], df_ventas_final)

                            # Actualizar el stock en la hoja "Productos"
                            nuevo_stock = stock_actual - cantidad_vendida
                            df_productos.loc[df_productos["Nombre"] == producto_seleccionado, "Stock"] = nuevo_stock
                            set_with_dataframe(worksheets["Productos"], df_productos)

                            st.success(f"Venta de {cantidad_vendida} x {producto_seleccionado} registrada. Nuevo stock: {nuevo_stock}.")
            else:
                st.warning("Primero debes registrar productos antes de poder registrar una venta.")
            
            st.markdown("---")
            st.subheader("Historial de Ventas")
            df_ventas_display = load_data(worksheets, "Ventas")
            if not df_ventas_display.empty:
                 st.dataframe(df_ventas_display, use_container_width=True)
            else:
                 st.info("Aún no se han registrado ventas.")


        # --- PÁGINA 3: REGISTRO DE COMPRAS ---
        elif opcion == "Registro de Compras":
            st.header("🛒 Registro de Compras (Entradas)")
            df_productos = load_data(worksheets, "Productos")

            if not df_productos.empty:
                lista_productos = df_productos["Nombre"].tolist()
                producto_seleccionado = st.selectbox("Selecciona un producto:", lista_productos)
                
                producto_info = df_productos[df_productos["Nombre"] == producto_seleccionado].iloc[0]
                
                with st.form("form_compra", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        cantidad_comprada = st.number_input("Cantidad Comprada", min_value=1, step=1)
                    with col2:
                        st.write(f"**Presentación:** {producto_info['Presentación']}")
                        st.write(f"**Stock Actual:** {producto_info['Stock']}")

                    submit_compra = st.form_submit_button("Registrar Compra")
                    
                    if submit_compra:
                        # Registrar la compra en la hoja "Compras"
                        fecha_compra = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        nueva_compra = pd.DataFrame([[fecha_compra, producto_info['ID_Producto'], producto_info['Nombre'], cantidad_comprada, producto_info['Presentación']]],
                                                    columns=["Fecha", "ID_Producto", "Nombre", "Cantidad", "Presentación"])
                        
                        df_compras_actual = load_data(worksheets, "Compras")
                        df_compras_final = pd.concat([df_compras_actual, nueva_compra], ignore_index=True)
                        set_with_dataframe(worksheets["Compras"], df_compras_final)

                        # Actualizar el stock en la hoja "Productos"
                        stock_actual = int(producto_info["Stock"])
                        nuevo_stock = stock_actual + cantidad_comprada
                        df_productos.loc[df_productos["Nombre"] == producto_seleccionado, "Stock"] = nuevo_stock
                        set_with_dataframe(worksheets["Productos"], df_productos)

                        st.success(f"Compra de {cantidad_comprada} x {producto_seleccionado} registrada. Nuevo stock: {nuevo_stock}.")
            else:
                st.warning("Primero debes registrar productos antes de poder registrar una compra.")

            st.markdown("---")
            st.subheader("Historial de Compras")
            df_compras_display = load_data(worksheets, "Compras")
            if not df_compras_display.empty:
                 st.dataframe(df_compras_display, use_container_width=True)
            else:
                 st.info("Aún no se han registrado compras.")

        # --- PÁGINA 4: DASHBOARD ---
        elif opcion == "Dashboard":
            st.header("📊 Dashboard de Inventario")

            # Cargar todos los datos
            df_productos = load_data(worksheets, "Productos")
            df_ventas = load_data(worksheets, "Ventas")
            df_compras = load_data(worksheets, "Compras")

            if df_productos.empty:
                st.warning("No hay datos de productos para mostrar en el dashboard.")
            else:
                # KPIs principales
                st.subheader("Indicadores Clave (KPIs)")
                total_productos = df_productos["ID_Producto"].nunique()
                total_stock = pd.to_numeric(df_productos["Stock"]).sum()
                
                # Asegurar que la columna Stock es numérica
                df_productos["Stock"] = pd.to_numeric(df_productos["Stock"], errors='coerce').fillna(0)
                productos_bajo_stock = df_productos[df_productos["Stock"] <= 10]

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(label="Total de Productos Únicos", value=total_productos)
                with col2:
                    st.metric(label="Total de Unidades en Stock", value=f"{total_stock:,.0f}")
                with col3:
                    st.metric(label="Productos con Bajo Stock (<=10)", value=len(productos_bajo_stock))

                if not productos_bajo_stock.empty:
                    with st.expander("Ver productos con bajo stock"):
                        st.dataframe(productos_bajo_stock[["Nombre", "Stock", "Categoría"]], use_container_width=True)

                st.markdown("---")
                st.subheader("Visualizaciones")

                # Columnas para los gráficos
                col_graf1, col_graf2 = st.columns(2)

                with col_graf1:
                    # Gráfico de Stock por Producto
                    st.write("**Niveles de Stock por Producto**")
                    if not df_productos.empty:
                        fig_stock = px.bar(
                            df_productos.sort_values("Stock", ascending=False),
                            x="Nombre",
                            y="Stock",
                            title="Stock por Producto",
                            color="Nombre",
                            labels={"Nombre": "Producto", "Stock": "Cantidad en Stock"}
                        )
                        fig_stock.update_layout(xaxis_title="", yaxis_title="Stock", showlegend=False)
                        st.plotly_chart(fig_stock, use_container_width=True)
                    else:
                        st.info("Sin datos de productos.")

                with col_graf2:
                    # Gráfico de Productos por Categoría
                    st.write("**Distribución de Productos por Categoría**")
                    if not df_productos.empty:
                        conteo_categoria = df_productos["Categoría"].value_counts().reset_index()
                        conteo_categoria.columns = ['Categoría', 'Cantidad']
                        fig_cat = px.pie(
                            conteo_categoria,
                            names="Categoría",
                            values="Cantidad",
                            title="Productos por Categoría",
                            hole=0.3
                        )
                        st.plotly_chart(fig_cat, use_container_width=True)
                    else:
                        st.info("Sin datos de categorías.")

                st.markdown("---")
                st.subheader("Análisis de Movimientos")
                
                col_mov1, col_mov2 = st.columns(2)
                
                with col_mov1:
                    st.write("**Top 5 Productos Más Vendidos**")
                    if not df_ventas.empty:
                        # Asegurar que la columna Cantidad es numérica
                        df_ventas['Cantidad'] = pd.to_numeric(df_ventas['Cantidad'], errors='coerce')
                        top_ventas = df_ventas.groupby("Nombre")["Cantidad"].sum().nlargest(5).reset_index()
                        fig_top_ventas = px.bar(
                            top_ventas,
                            x="Nombre",
                            y="Cantidad",
                            title="Top 5 Ventas",
                            color="Nombre"
                        )
                        fig_top_ventas.update_layout(xaxis_title="", yaxis_title="Unidades Vendidas", showlegend=False)
                        st.plotly_chart(fig_top_ventas, use_container_width=True)
                    else:
                        st.info("No hay registros de ventas.")

                with col_mov2:
                    st.write("**Top 5 Productos Más Comprados**")
                    if not df_compras.empty:
                        # Asegurar que la columna Cantidad es numérica
                        df_compras['Cantidad'] = pd.to_numeric(df_compras['Cantidad'], errors='coerce')
                        top_compras = df_compras.groupby("Nombre")["Cantidad"].sum().nlargest(5).reset_index()
                        fig_top_compras = px.bar(
                            top_compras,
                            x="Nombre",
                            y="Cantidad",
                            title="Top 5 Compras",
                            color="Nombre"
                        )
                        fig_top_compras.update_layout(xaxis_title="", yaxis_title="Unidades Compradas", showlegend=False)
                        st.plotly_chart(fig_top_compras, use_container_width=True)
                    else:
                        st.info("No hay registros de compras.")
