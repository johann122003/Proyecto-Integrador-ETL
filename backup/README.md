# Respaldo Físico de Base de Datos (`backup`)

Este directorio contiene la información del respaldo físico de la base de datos y DataMart **`DM_ComprasPublicas`** de **Microsoft SQL Server**.

---

## 💾 Archivo de Backup: `DM_ComprasPublicas.bak`

- **Tamaño:** ~250 MB (base de datos totalmente poblada con el histórico 2022–2026).
- **Control de Versiones:** El archivo `.bak` está excluido de los commits de Git mediante `.gitignore` debido al límite de 100 MB por archivo de GitHub. El archivo reside localmente en esta carpeta tras su generación.

---

## 🛠️ Instrucciones de Restauración en SQL Server Management Studio (SSMS)

### Opción A: Mediante la interfaz gráfica de SSMS
1. Abrir SQL Server Management Studio y conectarse a la instancia local de SQL Server.
2. En el Explorador de Objetos, hacer clic derecho sobre **Databases (Bases de datos)** > **Restore Database... (Restaurar base de datos...)**.
3. Seleccionar **Device (Dispositivo)**, hacer clic en los tres puntos `...`, luego en **Add (Agregar)** y buscar el archivo `backup/DM_ComprasPublicas.bak`.
4. Verificar que el nombre de la base de datos sea `DM_ComprasPublicas`.
5. En la pestaña **Options (Opciones)**, marcar `Overwrite the existing database (WITH REPLACE)` si ya existía una versión anterior.
6. Hacer clic en **OK**.

### Opción B: Mediante script Transact-SQL (T-SQL)
Ejecutar la siguiente instrucción ajustando la ruta hacia la ubicación del archivo `.bak` en su equipo:

```sql
RESTORE DATABASE DM_ComprasPublicas
FROM DISK = N'C:\ruta\al\repositorio\backup\DM_ComprasPublicas.bak'
WITH REPLACE, STATS = 10;
```

---

## 🔄 Alternativa: Reconstrucción desde Cero con Scripts
Si no se dispone del archivo `.bak`, la base de datos completa se puede regenerar limpiamente ejecutando:
1. `sql/ddl_datamart.sql` en SSMS (crea las tablas y dimensiones).
2. `sql/etl_watermark.sql` en SSMS (crea los procedimientos y marcas de agua).
3. `python etl/etl_load.py` en consola (puebla las dimensiones y la tabla de hechos incrementalmente).
