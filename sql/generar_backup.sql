/* ==========================================================================
   generar_backup.sql — Crea backup/DM_ComprasPublicas.bak
   Ejecutar en SSMS DESPUÉS de la carga completa (las 3 cargas de la demo).

   1. Cambia la ruta de abajo a la carpeta backup/ de la entrega.
      La cuenta del servicio de SQL Server necesita permiso de escritura ahí;
      si da "Access is denied", guarda primero en la carpeta Backup por
      defecto de SQL Server y luego copia el .bak.
   ========================================================================== */
BACKUP DATABASE DM_ComprasPublicas
TO DISK = N'C:\Users\antho\Documents\Entrega_ComprasPublicas\backup\DM_ComprasPublicas.bak'
WITH FORMAT, INIT, CHECKSUM, STATS = 10,   -- sin COMPRESSION: SQL Server Express no la soporta
     NAME = N'DM_ComprasPublicas - DataMart poblado 2022-2026';
GO

-- Verifica que el backup se pueda restaurar
RESTORE VERIFYONLY
FROM DISK = N'C:\Users\antho\Documents\Entrega_ComprasPublicas\backup\DM_ComprasPublicas.bak'
WITH CHECKSUM;
GO

/* Para restaurarlo en otra computadora (docente o P4):
RESTORE DATABASE DM_ComprasPublicas
FROM DISK = N'C:\ruta\DM_ComprasPublicas.bak'
WITH REPLACE, STATS = 10;
-- Si cambian las rutas de los archivos, agregar MOVE (ver RESTORE FILELISTONLY).
*/
