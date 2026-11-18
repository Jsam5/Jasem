(() => {
  const MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];

  const form = document.getElementById("ato-form");
  const output = document.getElementById("output");
  const statusEl = document.getElementById("status");
  const copyBtn = document.getElementById("copy");
  const printBtn = document.getElementById("print");
  const fillTodayBtn = document.getElementById("fill-today");
  const monthSelect = document.getElementById("month");
  const qualifierSelect = document.getElementById("qualifier");
  const chgSerial = document.getElementById("chgSerial");
  const locMode = document.getElementById("locMode");

  let latestText = "";

  function dash(value) {
    const v = String(value ?? "").trim();
    return v === "" ? "-" : v;
  }

  function field(value) {
    return String(value ?? "").trim().replace(/\s+/g, " ");
  }

  function setStatus(message, kind = "") {
    statusEl.textContent = message;
    statusEl.className = `status${kind ? ` ${kind}` : ""}`;
  }

  function pad2(n) {
    return String(n).padStart(2, "0");
  }

  function zuluStamp(date = new Date(), { withYear = true, endOfDay = false } = {}) {
    const d = pad2(date.getUTCDate());
    const h = endOfDay ? "2359" : pad2(date.getUTCHours()) + pad2(date.getUTCMinutes());
    const mon = MONTHS[date.getUTCMonth()];
    const y = String(date.getUTCFullYear()).slice(-2);
    return withYear ? `${d}${h}Z${mon}${y}` : `${d}${h}Z${mon}`;
  }

  function fillMonthOptions() {
    const now = new Date();
    monthSelect.innerHTML = MONTHS.map((m) => `<option value="${m}">${m}</option>`).join("");
    monthSelect.value = MONTHS[now.getUTCMonth()];
  }

  function fillTodayDefaults() {
    const now = new Date();
    document.getElementById("periodFrom").value = zuluStamp(now, { withYear: true });
    document.getElementById("periodTo").value = zuluStamp(now, { withYear: true, endOfDay: true });
    document.getElementById("tot").value = zuluStamp(now, { withYear: false });
    const net = new Date(now.getTime() - 5 * 60 * 1000);
    const nlt = new Date(now.getTime() + 2 * 60 * 60 * 1000);
    document.getElementById("net").value = zuluStamp(net, { withYear: false });
    document.getElementById("nlt").value = zuluStamp(nlt, { withYear: false });
    monthSelect.value = MONTHS[now.getUTCMonth()];
    setStatus("تم تعبئة توقيت اليوم بتوقيت Zulu.", "ok");
  }

  function syncQualifier() {
    const isChg = qualifierSelect.value === "CHG";
    chgSerial.disabled = !isChg;
    if (!isChg) chgSerial.value = "";
    else if (!chgSerial.value.trim()) chgSerial.value = "1";
  }

  function syncLocMode() {
    const ground = locMode.value === "GTGTLOC";
    document.getElementById("tgtId").closest("label").hidden = !ground;
    document.getElementById("dmpi").closest("label").hidden = !ground;
    document.getElementById("altitude").closest("label").hidden = ground;
  }

  function buildAto(data) {
    const lines = [];
    const kind = data.msgKind === "EXER" ? "EXER" : "OPER";
    lines.push(`${kind}/${field(data.operation)}//`);

    const msgid = ["MSGID", "ATO", field(data.originator), field(data.serial), field(data.month)];
    if (data.qualifier === "CHG") {
      msgid.push("CHG", dash(data.chgSerial));
    } else {
      msgid.push("INI", "-");
    }
    lines.push(`${msgid.join("/")}//`);

    lines.push(`AKNLDG/${data.ack}//`);
    lines.push(`PERIOD/FROM:${field(data.periodFrom)}/TO:${field(data.periodTo)}//`);

    const unitLoc = field(data.unitLoc);
    const unitLocField = /^[A-Z0-9]{4}$/i.test(unitLoc) ? `ICAO:${unitLoc.toUpperCase()}` : unitLoc;
    lines.push(`TASKUNIT/${field(data.taskUnit)}/${unitLocField}//`);

    const amsndat = [
      "AMSNDAT",
      field(data.msnNum),
      "-",
      dash(data.package),
      data.mc || "-",
      field(data.msnType),
      dash(data.msnType2),
      dash(data.alert),
      `DEPLOC:${field(data.depLoc).toUpperCase()}`,
      `ARRLOC:${field(data.arrLoc).toUpperCase()}`,
    ];
    lines.push(`${amsndat.join("/")}//`);

    const acMatch = field(data.acCountType).match(/^(\d+)\s*([A-Za-z][A-Za-z0-9-]*)$/);
    if (acMatch) {
      lines.push(
        `MSNACFT/${acMatch[1]}/ACTYP:${acMatch[2].toUpperCase()}/${field(data.callsign)}/${dash(data.config1)}/${dash(data.config2)}/-/${dash(data.iff)}//`
      );
    } else {
      lines.push(
        `MSNACFT/${field(data.acCountType)}/${field(data.callsign)}/${dash(data.config1)}/${dash(data.config2)}/-/${dash(data.iff)}//`
      );
    }

    if (data.locMode === "GTGTLOC") {
      const gt = [
        "GTGTLOC",
        "P",
        `TOT:${field(data.tot)}`,
        `NET:${dash(data.net)}`,
        `NLT:${dash(data.nlt)}`,
        field(data.locName),
        data.tgtId ? `ID:${field(data.tgtId)}` : "-",
        "-",
        "-",
        data.dmpi ? `DMPIS:${field(data.dmpi)}` : "-",
        "-",
        "-",
        "-",
        dash(data.priority),
      ];
      lines.push(`${gt.join("/")}//`);
    } else {
      lines.push(
        `AMSNLOC/${field(data.tot)}/${dash(data.nlt)}/${field(data.locName)}/${dash(data.altitude)}/${dash(data.priority)}//`
      );
    }

    if (field(data.ctrlCall) || field(data.ctrlFreq)) {
      lines.push(
        `CONTROLA/-/${dash(data.ctrlCall)}/${dash(data.ctrlFreq)}/-/-/-//`
      );
    }

    if (field(data.narr)) {
      lines.push(`NARR/${field(data.narr)}//`);
    }

    return lines.join("\n");
  }

  function readForm() {
    const fd = new FormData(form);
    const data = Object.fromEntries(fd.entries());
    return data;
  }

  function validate(data) {
    const required = [
      ["operation", "اسم العملية"],
      ["originator", "الجهة المصدرة"],
      ["serial", "رقم الرسالة"],
      ["periodFrom", "من"],
      ["periodTo", "إلى"],
      ["taskUnit", "اسم الوحدة"],
      ["unitLoc", "الموقع"],
      ["msnNum", "رقم المهمة"],
      ["depLoc", "مغادرة"],
      ["arrLoc", "عودة"],
      ["acCountType", "عدد ونوع الطائرات"],
      ["callsign", "النداء"],
      ["tot", "بداية / TOT"],
      ["locName", "اسم المنطقة / الهدف"],
    ];
    for (const [key, label] of required) {
      if (!field(data[key])) return `الرجاء تعبئة: ${label}`;
    }
    if (data.qualifier === "CHG" && !field(data.chgSerial)) {
      return "رقم التعديل مطلوب عند اختيار CHG";
    }
    return "";
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = readForm();
    const error = validate(data);
    if (error) {
      setStatus(error, "err");
      copyBtn.disabled = true;
      printBtn.disabled = true;
      return;
    }

    latestText = buildAto(data);
    output.textContent = latestText;
    output.classList.remove("ready");
    void output.offsetWidth;
    output.classList.add("ready");
    copyBtn.disabled = false;
    printBtn.disabled = false;
    setStatus("الأمر جاهز — انسخه أو اطبعه.", "ok");
  });

  copyBtn.addEventListener("click", async () => {
    if (!latestText) return;
    try {
      await navigator.clipboard.writeText(latestText);
      setStatus("تم النسخ إلى الحافظة.", "ok");
    } catch {
      const range = document.createRange();
      range.selectNodeContents(output);
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      setStatus("تعذر النسخ التلقائي — حدّد النص وانسخه يدوياً.", "err");
    }
  });

  printBtn.addEventListener("click", () => {
    if (!latestText) return;
    window.print();
  });

  fillTodayBtn.addEventListener("click", fillTodayDefaults);
  qualifierSelect.addEventListener("change", syncQualifier);
  locMode.addEventListener("change", syncLocMode);

  form.addEventListener("reset", () => {
    setTimeout(() => {
      fillMonthOptions();
      fillTodayDefaults();
      syncQualifier();
      syncLocMode();
      latestText = "";
      output.textContent = "اضغط Generate ATO لعرض الأمر هنا.";
      output.classList.remove("ready");
      copyBtn.disabled = true;
      printBtn.disabled = true;
      setStatus("تمت إعادة التعيين.");
    }, 0);
  });

  fillMonthOptions();
  fillTodayDefaults();
  syncQualifier();
  syncLocMode();
})();
