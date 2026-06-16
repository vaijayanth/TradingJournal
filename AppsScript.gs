function colToIndex(col) {
  col = col.toUpperCase().trim();
  let n = 0;
  for (let i = 0; i < col.length; i++) n = n * 26 + (col.charCodeAt(i) - 64);
  return n - 1;
}

function doGet(e) {
  try {
    const p = e.parameter;
    const ss = SpreadsheetApp.getActiveSpreadsheet();

    // ── F&O MODE ──────────────────────────────────────────────
    if (p.mode === 'fno') {
      const sheet = ss.getSheetByName('NSEFO');
      const data  = sheet.getDataRange().getValues();
      const watchlist = [];
      for (let i = 1; i < data.length; i++) {
        const row = data[i];
        if (!row[6] || String(row[6]).trim() === '') continue;
        const stock  = String(row[6]).trim().replace('NSE:','').replace('BSE:','');
        const cmp    = parseFloat(row[7]) || 0;
        const gapRaw = String(row[17]).trim();
        watchlist.push({
          stock,
          broker:      String(row[5]).trim(),
          cmp,
          ema200:      String(row[8]).trim().toLowerCase()  === 'yes',
          ema50:       String(row[9]).trim().toLowerCase()  === 'yes',
          ema20:       String(row[10]).trim().toLowerCase() === 'above',
          haColour:    String(row[11]).trim(),
          haChanged:   (row[12] === true || String(row[12]).toUpperCase() === 'TRUE'),
          ath:         String(row[13]).trim().toLowerCase() === 'yes',
          wk52h:       String(row[14]).trim().toLowerCase() === 'yes',
          dh21:        String(row[15]).trim().toLowerCase() === 'yes',
          dh7:         String(row[16]).trim().toLowerCase() === 'yes',
          hasGapUp:    gapRaw && gapRaw !== '0' && gapRaw.toLowerCase() !== 'no' && gapRaw !== '',
          gapUp:       gapRaw,
          ema200cross: String(row[18]).trim().toLowerCase() === 'yes',
          ema50cross:  String(row[19]).trim().toLowerCase() === 'yes',
          ema21cross:  String(row[20]).trim().toLowerCase() === 'yes',
          sevenDayLow: parseFloat(row[21]) || 0,
          pctFrom7DL:  String(row[22]).trim(),
          spreadActive:(row[23] === true || String(row[23]).toUpperCase() === 'TRUE'),
        });
      }
      return ContentService
        .createTextOutput(JSON.stringify({ success: true, watchlist, fetchedAt: new Date().toISOString() }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    // ── SWING MODE ────────────────────────────────────────────
    const sheet = ss.getSheetByName(p.sheet || 'TRADES');
    const data  = sheet.getDataRange().getValues();
    const toNum = v => { const n=parseFloat(v); return isNaN(n)?0:n; };
    const toPct = v => { const n=parseFloat(v); return isNaN(n)?0:Math.round(n*10000)/100; };
    const toVal = v => { const s=String(v).trim(); if(!s||s===' ')return 0; const n=parseFloat(s); return isNaN(n)?0:n; };
    const c = {
      flag:           colToIndex(p.flagCol           || 'B'),
      stock:          colToIndex(p.stockCol          || 'E'),
      openDate:       colToIndex(p.openDateCol       || 'C'),
      closeDate:      colToIndex(p.closeDateCol      || 'D'),
      ema21:          colToIndex(p.ema21Col          || 'F'),
      cmp:            colToIndex(p.cmpCol            || 'H'),
      sevenDayLow:    colToIndex(p.sevenDayLowCol    || 'I'),
      stopLoss:       colToIndex(p.stopLossCol       || 'J'),
      initRiskRs:     colToIndex(p.initRiskRsCol     || 'K'),
      initRiskPct:    colToIndex(p.initRiskPctCol    || 'L'),
      qty:            colToIndex(p.qtyCol            || 'Q'),
      entryPrice:     colToIndex(p.entryPriceCol     || 'R'),
      setupType:      colToIndex(p.setupTypeCol      || 'S'),
      pctFromStop:    colToIndex(p.pctFromStopCol    || 'W'),
      plPct:          colToIndex(p.plPctCol          || 'X'),
      notionalPl:     colToIndex(p.notionalPlCol     || 'Y'),
      partialQty:     colToIndex(p.partialQtyCol     || 'Z'),
      partialPrice:   colToIndex(p.partialPriceCol   || 'AA'),
      partialPl:      colToIndex(p.partialPlCol      || 'AB'),
      finalExitPrice: colToIndex(p.finalExitPriceCol || 'AC'),
      finalPl:        colToIndex(p.finalPlCol        || 'AD'),
      finalPlPct:     colToIndex(p.finalPlPctCol     || 'AE'),
      age:            colToIndex(p.ageCol            || 'AF'),
      haColour:       colToIndex(p.haColourCol       || 'AG'),
      haChanged:      colToIndex(p.haChangedCol      || 'AH'),
      mae:            colToIndex(p.maeCol            || 'AL'),
      mfe:            colToIndex(p.mfeCol            || 'AM'),
    };
    const skipRows = parseInt(p.headerRows || '1');
    const open = [], closed = [];
    for (let i = skipRows; i < data.length; i++) {
      const row  = data[i];
      const flag = String(row[c.flag]).trim().toUpperCase();
      if (flag !== 'YES' && flag !== 'NO') continue;
      const stock = String(row[c.stock]).trim().replace('NSE:','').replace('BSE:','');
      const trade = {
        flag, stock,
        openDate:       row[c.openDate]  ? Utilities.formatDate(new Date(row[c.openDate]),  Session.getScriptTimeZone(), 'dd-MMM-yyyy') : '',
        closeDate:      row[c.closeDate] ? Utilities.formatDate(new Date(row[c.closeDate]), Session.getScriptTimeZone(), 'dd-MMM-yyyy') : '',
        ema21:          String(row[c.ema21]).trim(),
        cmp:            toNum(row[c.cmp]),
        sevenDayLow:    toNum(row[c.sevenDayLow]),
        stopLoss:       toNum(row[c.stopLoss]),
        initRiskRs:     toNum(row[c.initRiskRs]),
        initRiskPct:    toPct(row[c.initRiskPct]),
        qty:            toNum(row[c.qty]),
        entryPrice:     toNum(row[c.entryPrice]),
        setupType:      String(row[c.setupType]).trim(),
        pctFromStop:    toPct(row[c.pctFromStop]),
        plPct:          toPct(row[c.plPct]),
        notionalPl:     toVal(row[c.notionalPl]),
        partialQty:     toNum(row[c.partialQty]),
        partialPrice:   toNum(row[c.partialPrice]),
        partialPl:      toVal(row[c.partialPl]),
        finalExitPrice: toNum(row[c.finalExitPrice]),
        finalPl:        toVal(row[c.finalPl]),
        finalPlPct:     toVal(row[c.finalPlPct]) !== 0 ? toPct(row[c.finalPlPct]) : 0,
        age:            toNum(row[c.age]),
        partialTaken:   toNum(row[c.partialQty]) > 0 ? 'Y' : 'N',
        haColour:       String(row[c.haColour]).trim(),
        haChanged:      (row[c.haChanged] === true || String(row[c.haChanged]).toUpperCase() === 'TRUE') ? 'Y' : 'N',
        mae:            toNum(row[c.mae]),
        mfe:            toNum(row[c.mfe]),
      };
      if (trade.entryPrice === 0) continue;
      if (trade.initRiskRs < 0) trade.dataError = 'Negative risk';
      if (trade.age > 500)      trade.dataError = 'Missing date';
      if (flag === 'YES')                             open.push(trade);
      else if (flag === 'NO' && trade.finalPl !== 0) closed.push(trade);
    }
    const portfolioValue = toNum(sheet.getRange(p.portfolioCell  || 'AK26').getValue());
    const initialCapital = toNum(sheet.getRange(p.initialCapCell || 'AK20').getValue());
    const signalRunAt    = sheet.getRange('AK31').getDisplayValue();   // ← NEW
    return ContentService
      .createTextOutput(JSON.stringify({ success: true, portfolioValue, initialCapital, open, closed, fetchedAt: new Date().toISOString(), signalRunAt }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch(err) {
    return ContentService
      .createTextOutput(JSON.stringify({ success: false, error: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
