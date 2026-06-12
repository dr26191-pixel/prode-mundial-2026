// ─────────────────────────────────────────────────────────────────
// GiPA – Encuesta de Satisfacción · Google Apps Script
//
// CÓMO USARLO:
//  1. Ir a https://script.google.com → Nuevo proyecto
//  2. Pegar TODO este código (reemplazar el contenido vacío)
//  3. Menú: Implementar → Nueva implementación
//     · Tipo: Aplicación web
//     · Ejecutar como: Yo (tu cuenta)
//     · Quién tiene acceso: Cualquier usuario
//  4. Copiar la URL que aparece al final
//  5. Pegarla en index.html donde dice PEGA_AQUI_TU_URL
// ─────────────────────────────────────────────────────────────────

const NOMBRE_HOJA = 'base satisfaccion';

const ENCABEZADOS = [
  'Fecha y hora',
  'Nombre',
  'Empresa',
  'Cargo',
  'Sector',
  'Primera vez en plenaria',
  'Eval. Utilidad informaciones',
  'Eval. Interés plenaria',
  'Eval. Calidad análisis',
  'Eval. Orador',
  'Eval. Diapositivas',
  'Eval. Material entregado',
  'Duración',
  'Utilidad de la visita',
  'Por qué (utilidad)',
  'Satisfacción general',
  'Razón insatisfacción',
  'Slide interés 1°',
  'Slide interés 2°',
  'Slide interés 3°',
  'Áreas a investigar',
  'Sugerencias',
];

function doPost(e) {
  try {
    var ss    = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName(NOMBRE_HOJA);

    // Crear hoja si no existe
    if (!sheet) {
      sheet = ss.insertSheet(NOMBRE_HOJA);
    }

    // Escribir encabezados si la hoja está vacía
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(ENCABEZADOS);
      var headerRange = sheet.getRange(1, 1, 1, ENCABEZADOS.length);
      headerRange.setFontWeight('bold');
      headerRange.setBackground('#3A3A3A');
      headerRange.setFontColor('#FFFFFF');
      sheet.setFrozenRows(1);
    }

    var d = JSON.parse(e.postData.contents);

    sheet.appendRow([
      new Date().toLocaleString('es-AR'),
      d.nombre                || '',
      d.empresa               || '',
      d.cargo                 || '',
      d.sector                || '',
      d.primera_vez           || '',
      d.eval_utilidad         || '',
      d.eval_interes          || '',
      d.eval_calidad_analisis || '',
      d.eval_orador           || '',
      d.eval_diapositivas     || '',
      d.eval_material         || '',
      d.duracion              || '',
      d.utilidad_visita       || '',
      d.porque_utilidad       || '',
      d.satisfaccion_general  || '',
      d.razon_insatisfaccion  || '',
      d.slide1                || '',
      d.slide2                || '',
      d.slide3                || '',
      d.areas_investigacion   || '',
      d.sugerencias           || '',
    ]);

    return ContentService
      .createTextOutput(JSON.stringify({ status: 'ok' }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ status: 'error', message: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
