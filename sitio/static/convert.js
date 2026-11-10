/* SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
   Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE). */
// Open Well Data conversion engine, browser and Node. A line-by-line port of owd/owd/convert.py driven by the same
// tables (data/convert-tables.json, written by sitio/build.py from owd.convert.tables()). Any change must be made in
// both files; owd/tests/parity checks that both give byte-identical CSV and LAS and the same provenance.
// No dependencies. Nothing is sent anywhere: the caller passes the file text and gets the output text back.
(function (root) {
  "use strict";

  var SITE = "https://openwelldata.org";
  var DEFAULT_DIGITS = 12;
  var NUM = /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/;
  var HDR_UNIT = /^(.*?)\s*[\(\[]([^()\[\]]*)[\)\]]\s*$/;

  function ConversionError(msg) { var e = new Error(msg); e.name = "ConversionError"; return e; }
  function strip(s) { return String(s == null ? "" : s).trim(); }
  function rstrip(s) { return s.replace(/\s+$/, ""); }
  function has(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }

  // ---------------------------------------------------------------- index
  function Index(t) {
    var self = this;
    this.t = t; this.units = t.units; this.exact = {}; this.lower = {}; this.mnem = {}; this.std = {};
    this.unknown = {}; t.unknown_units.forEach(function (u) { self.unknown[u] = true; });
    this.units.forEach(function (u, i) {
      [u.symbol].concat(u.aliases).forEach(function (s) {
        var a = has(self.exact, s) ? self.exact[s] : (self.exact[s] = []);
        if (a.indexOf(i) < 0) a.push(i);
        var l = s.toLowerCase(), b = has(self.lower, l) ? self.lower[l] : (self.lower[l] = []);
        if (b.indexOf(i) < 0) b.push(i);
      });
      var k = u.dimension + "\u0000" + u.symbol;
      if (!has(self.std, k)) self.std[k] = i;
    });
    Object.keys(t.variables).forEach(function (v) {
      t.variables[v].mnemonics.forEach(function (m) {
        var k = m.toUpperCase(), a = has(self.mnem, k) ? self.mnem[k] : (self.mnem[k] = []);
        if (a.indexOf(v) < 0) a.push(v);
      });
    });
    // statistic rules (channel_statistics.tsv), case-insensitive, same syntax as the Python re patterns
    this.statRules = (t.statistics || []).map(function (r) {
      var o = {}; Object.keys(r).forEach(function (k) { o[k] = r[k]; });
      o.rx = (r.kind === "window" || r.kind === "exclude" || r.kind === "description") ? new RegExp(r.pattern, "i") : null;
      return o;
    });
    this.version = t.meta.dictionary_version;
  }

  // ---------------------------------------------------------------- units
  function isNoUnit(ix, s) {
    s = strip(s);
    return has(ix.unknown, s) || /^[-.]*$/.test(s) || s.indexOf("BAD_UNIT") === 0;
  }

  function resolveUnit(ix, s, dimension) {
    s = strip(s);
    if (isNoUnit(ix, s)) return { status: "none", dimensions: [] };
    var cands = has(ix.exact, s) ? ix.exact[s] : null, how = "exact";
    if (!cands || !cands.length) { cands = has(ix.lower, s.toLowerCase()) ? ix.lower[s.toLowerCase()] : null; how = "case-insensitive"; }
    if (!cands || !cands.length) return { status: "unknown", dimensions: [] };
    var dims = [];
    cands.forEach(function (i) { var d = ix.units[i].dimension; if (dims.indexOf(d) < 0) dims.push(d); });
    if (dimension) {
      var f = cands.filter(function (i) { return ix.units[i].dimension === dimension; });
      if (!f.length) return { status: "mismatch", dimensions: dims, match: how };
      cands = f;
    }
    var u0 = ix.units[cands[0]];
    for (var j = 1; j < cands.length; j++) {
      var u = ix.units[cands[j]];
      if (u.base !== u0.base || u.factor !== u0.factor || u.offset !== u0.offset || u.dimension !== u0.dimension)
        return { status: "ambiguous", dimensions: dims, match: how };
    }
    return { status: "ok", unit: cands[0], dimensions: dims, match: how };
  }

  function factorOffset(src, dst) {
    if (src === dst || (src.factor === dst.factor && src.offset === dst.offset)) return [1, 0];
    return [src.factor / dst.factor, (src.offset - dst.offset) / dst.factor];
  }

  function applyLinear(x, b) {
    if (b[1] === 0 && b[3] === 0) return x * b[0] / b[2];
    return (x * b[0] + b[1] - b[3]) / b[2];
  }

  function unitRow(ix, symbol, dimension) {
    var k = dimension + "\u0000" + symbol, i = has(ix.std, k) ? ix.std[k] : null;
    if (i === null) { var r = resolveUnit(ix, symbol, dimension); i = r.status === "ok" ? r.unit : null; }
    return i === null ? null : ix.units[i];
  }

  function unitsOf(ix, dimension, base) {
    return ix.units.filter(function (u) { return u.dimension === dimension && (base == null || u.base === base); })
      .map(function (u) { return u.symbol; });
  }

  // ---------------------------------------------------------------- numbers (same text as Python fmt_number)
  function fmtNumber(x, digits) {
    if (digits) x = Number(x.toPrecision(digits));
    if (x === 0) return "0";
    return String(x);
  }
  function parseNumber(tok) { tok = strip(tok); return NUM.test(tok) ? Number(tok) : null; }

  // ---------------------------------------------------------------- mapping
  function compat(t, a, b) { return a === b || (t.ratio_dimensions.indexOf(a) >= 0 && t.ratio_dimensions.indexOf(b) >= 0); }
  function lookupKey(name) { return strip(name == null ? "" : name).replace(/:\d+$/, "").toUpperCase(); }
  function stripUnitSuffix(name) { return String(name).replace(/\s*[\(\[][^()\[\]]*[\)\]]\s*$/, "").trim(); }
  function isLog(t, fmt) { return t.log_formats.indexOf(fmt) >= 0; }

  // A context rule whose variable is UNASSIGNED keeps the mnemonic out of every variable (no fallback to the name).
  var UNASSIGNED = "-";
  // A variable of a difference dimension takes a declared unit of the paired absolute dimension by scale only.
  var DIFFERENCE_DIMS = { temperature_difference: "temperature" };
  function normDataset(d) { return strip(d == null ? "" : d).toLowerCase().replace(/_/g, "-"); }
  function datasetMatches(want, dataset) {
    if (!want || !want.length) return true;
    var ds = normDataset(dataset);
    if (!ds) return false;
    return want.some(function (w) { w = normDataset(w); return w === "*" || ds === w || ds.indexOf(w + "-") === 0; });
  }

  function contextVariable(ix, key, dims, sourceFormat, dataset) {
    var t = ix.t, fmt = String(sourceFormat || "").toUpperCase(), rows = has(t.context, key) ? t.context[key] : [];
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i], want = r.when_unit_dimension;
      if (want.length && !want.some(function (w) {
        return (!dims.length && w === "unknown") || (dims.length && dims.some(function (d) { return compat(t, d, w); }));
      })) continue;
      var src = r.when_source;
      if (src.length && !src.some(function (w) {
        return (w === "log" && isLog(t, fmt)) || (w === "table" && !isLog(t, fmt)) || w === fmt;
      })) continue;
      if (!datasetMatches(r.when_dataset || [], dataset)) continue;
      return [r.variable, r];
    }
    return [null, null];
  }

  function mapChannel(ix, name, unit, sourceFormat, dataset) {
    var t = ix.t, raw = strip(name == null ? "" : name), key = lookupKey(raw), warnings = [];
    if (has(t.variables, raw)) return [raw, "standard_name", null, []];
    var q = QUALIFIED_NAME.exec(raw);
    if (q && has(t.variables, q[1])) return [q[1], "standard_name", null, []];
    if (has(t.context, key)) {
      var r = resolveUnit(ix, unit, null);
      var cv = contextVariable(ix, key, r.status !== "unknown" ? r.dimensions : [], sourceFormat, dataset);
      if (cv[0] === UNASSIGNED)
        return [null, "context_unassigned", { when_unit_dimension: cv[1].when_unit_dimension, when_source: cv[1].when_source,
          when_dataset: cv[1].when_dataset || [], note: cv[1].note },
          ["a context rule keeps " + key + " out of every variable here (" + cv[1].note + "): kept with its original name, " +
           "values unchanged"]];
      if (cv[0]) {
        if (has(t.variables, cv[0]))
          return [cv[0], "context_rule", { when_unit_dimension: cv[1].when_unit_dimension, when_source: cv[1].when_source,
            when_dataset: cv[1].when_dataset || [], note: cv[1].note }, []];
        warnings.push("context rule points to '" + cv[0] + "', which is not a variable of the dictionary");
      }
    }
    var cands = has(ix.mnem, key) ? ix.mnem[key] : [];
    if (cands.length === 1) return [cands[0], "dictionary", null, warnings];
    if (cands.length > 1) {
      warnings.push(key + " is listed under several variables (" + cands.join(", ") + ") and no context rule decides " +
        "(pass the source format, or the unit); kept with its original name");
      return [null, "ambiguous", { candidates: cands }, warnings];
    }
    var al = stripUnitSuffix(raw).toLowerCase(), a = has(t.aliases, al) ? t.aliases[al] : null;
    if (a && has(t.variables, a)) return [a, "channel_alias", null, warnings];
    return [null, null, null, warnings];
  }

  // ---------------------------------------------------------------- statistic of a channel (same as Python)
  var QUALIFIED_STATISTICS = ["mean", "max", "min", "std", "median", "rms"];
  var QUALIFIED_NAME = new RegExp("^(.+)_(" + QUALIFIED_STATISTICS.join("|") + ")$");

  function channelStatistic(ix, name, description, v) {
    var t = ix.t;
    if (!v || !has(t.variables, v)) return [null, null, null, []];
    var dim = t.variables[v].dimension;
    var rules = ix.statRules.filter(function (r) { return r.not_dimension.indexOf(dim) < 0; });
    var key = lookupKey(stripUnitSuffix(String(name == null ? "" : name)));
    var byName = [], byDesc = [];
    var toks = key.split(/[^A-Z0-9]+/).filter(function (x) { return x !== ""; });
    rules.forEach(function (r) {
      var s = r.statistic;
      if (r.kind === "name_token") {
        if (toks.length > 1 && toks.indexOf(r.pattern) >= 0 && byName.indexOf(s) < 0) byName.push(s);
      } else if (r.kind === "name_suffix" && key.length > r.pattern.length &&
                 key.slice(key.length - r.pattern.length) === r.pattern) {
        var stem = key.slice(0, key.length - r.pattern.length).replace(/[_\-. ]+$/, "");
        if (stem && (stem === v.toUpperCase() || (has(ix.mnem, stem) && ix.mnem[stem].indexOf(v) >= 0)) &&
            byName.indexOf(s) < 0) byName.push(s);
      }
    });
    var desc = String(description || ""), win = null;
    if (strip(desc)) {
      rules.forEach(function (r) {
        if (r.kind === "window" && win === null) {
          var m = r.rx.exec(desc);
          if (m) win = r.window.replace("{1}", m.length > 1 && m[1] !== undefined ? m[1] : "");
        }
      });
      var d = desc;
      rules.forEach(function (r) { if (r.kind === "exclude") d = d.replace(new RegExp(r.pattern, "gi"), " "); });
      rules.forEach(function (r) {
        if (r.kind === "description" && r.rx.test(d) && byDesc.indexOf(r.statistic) < 0) byDesc.push(r.statistic);
      });
    }
    var warnings = [];
    if (byName.length > 1 || (!byName.length && byDesc.length > 1))
      return ["unspecified", null, "conflict", ["statistic unclear: the name says " + (byName.join(", ") || "nothing") +
        " and the description says " + (byDesc.join(", ") || "nothing") + "; written without a statistic qualifier"]];
    var st, ev;
    if (byName.length) {
      st = byName[0];
      if (!byDesc.length) ev = "name";
      else if (byDesc.length === 1 && byDesc[0] === st) ev = "name+description";
      else {
        ev = "name_over_description";
        warnings.push("the name says " + st + " but the description says " + byDesc.join(", ") + ": written as " + st +
          " (statistic word in the name); check the values");
      }
    } else if (byDesc.length) { st = byDesc[0]; ev = "description"; }
    else return ["unspecified", null, null, []];
    return [st, QUALIFIED_STATISTICS.indexOf(st) >= 0 ? win : null, ev, warnings];
  }

  function qualifiedName(v, st) { return QUALIFIED_STATISTICS.indexOf(st) >= 0 ? v + "_" + st : v; }

  // statistic that goes into the name: always for qualify_family variables (drilling, mud_gas); for other families only
  // when two different qualified statistics of one variable coexist in the file (same as Python naming_statistics)
  function namingStatistics(ix, plans) {
    var t = ix.t, fams = {}, seen = {};
    (t.statistics || []).forEach(function (r) { if (r.kind === "qualify_family") fams[r.pattern] = true; });
    plans.forEach(function (p) {
      if (p.variable && QUALIFIED_STATISTICS.indexOf(p.statistic) >= 0) {
        var l = has(seen, p.variable) ? seen[p.variable] : (seen[p.variable] = []);
        if (l.indexOf(p.statistic) < 0) l.push(p.statistic);
      }
    });
    return plans.map(function (p) {
      if (!p.variable || QUALIFIED_STATISTICS.indexOf(p.statistic) < 0) return null;
      var fam = has(t.variables, p.variable) ? t.variables[p.variable].family : null;
      return (has(fams, fam) || seen[p.variable].length > 1) ? p.statistic : null;
    });
  }

  function lasSafe(s, fallback) {
    s = String(s == null ? "" : s).replace(/[\s.:~#]+/g, "_").replace(/^_+|_+$/g, "");
    return s || fallback;
  }
  function lasUnit(s) { return strip(s).replace(/\s+/g, "_"); }

  function targetUnit(ix, v, units) {
    var V = ix.t.variables[v], def = typeof units === "string" ? units : "si";
    if (units && typeof units === "object") {
      def = units._default || "si";
      if (has(units, v)) {
        var row = unitRow(ix, units[v], V.dimension), std = unitRow(ix, V.unit, V.dimension);
        if (!row || !std || row.base !== std.base)
          throw ConversionError(v + ": cannot convert to '" + units[v] + "' (a " + V.dimension + " variable; units: " +
            unitsOf(ix, V.dimension, std ? std.base : null).join(", ") + ")");
        return row.symbol;
      }
    }
    if (def === "si") return V.unit;
    if (def === "field") {
      var p = ix.t.presets.field;
      return (has(p.variable, v) && p.variable[v]) || (has(p.dimension, V.dimension) && p.dimension[V.dimension]) || V.unit;
    }
    throw ConversionError("units must be 'si', 'field' or an object");
  }

  function unitsLabel(units) {
    if (units && typeof units === "object") return (units._default || "si") === "si" ? "custom" : "custom:" + units._default;
    return units;
  }

  function ruleFor(ix, key, v, unit, res) {
    var rules = ix.t.rules;
    for (var i = 0; i < rules.length; i++) {
      var r = rules[i];
      if (r.mnemonic !== key || r.variable !== v) continue;
      for (var j = 0; j < r.when_unit.length; j++) {
        var w = r.when_unit[j];
        if ((w === "none" && res.status === "none") || (w === "dimensionless" && res.dimensions.indexOf("dimensionless") >= 0) ||
          w === strip(unit)) return r;
      }
    }
    return null;
  }

  function planChannels(ix, channels, names, units, sourceFormat, output, dataset) {
    var t = ix.t;
    if (names !== "owd" && names !== "original") throw ConversionError("names must be 'owd' or 'original'");
    var plans = channels.map(function (ch) {
      var name = String(ch.name == null ? "" : ch.name), unit = strip(ch.unit || ""), key = lookupKey(name);
      var p = { original_name: name, original_unit: unit, description: String(ch.description || ""), variable: null,
        candidate_variable: null, mapped_by: null, context_rule: null, status: "unmapped", name: name, unit: unit,
        factor: 1, offset: 0, base_factors: null, converted: false, unit_rule: null, unit_note: "", statistic: null,
        window: null, statistic_evidence: null, warnings: [] };
      var m = mapChannel(ix, name, unit, sourceFormat, dataset), v = m[0], how = m[1];
      p.warnings = p.warnings.concat(m[3]);
      if (how === "ambiguous") p.status = "ambiguous_mnemonic";
      if (how === "context_unassigned") { p.mapped_by = how; p.context_rule = m[2]; }
      if (v === null && how !== "ambiguous" && how !== "context_unassigned") p.warnings.push("not in the dictionary: kept with its original name, values unchanged");
      if (v !== null) {
        var V = t.variables[v], dim = V.dimension;
        p.candidate_variable = v; p.mapped_by = how;
        if (how === "context_rule") p.context_rule = m[2];
        var res = resolveUnit(ix, unit, dim), rule = ruleFor(ix, key, v, unit, res);
        if (rule && rule.action === "assume_unit") {
          res = resolveUnit(ix, rule.unit, dim);
          p.unit_rule = { action: rule.action, unit: rule.unit, note: rule.note, source: rule.source };
        }
        var tgtSym = targetUnit(ix, v, units), diffRow = null;
        if (res.status === "mismatch" && has(DIFFERENCE_DIMS, dim) && res.dimensions.indexOf(DIFFERENCE_DIMS[dim]) >= 0) {
          var r2 = resolveUnit(ix, p.unit_rule ? rule.unit : unit, DIFFERENCE_DIMS[dim]), tgt0 = unitRow(ix, tgtSym, dim);
          if (r2.status === "ok" && tgt0) {
            var a = ix.units[r2.unit];
            diffRow = {};
            Object.keys(a).forEach(function (k) { diffRow[k] = a[k]; });
            diffRow.offset = 0; diffRow.base = tgt0.base; diffRow.dimension = dim;
            diffRow.note = (a.note ? a.note + "; " : "") + "read as a difference: scale only, no offset";
            res = { status: "ok", unit: null, dimensions: [dim], match: r2.match };
            p.warnings.push("unit '" + unit + "' read as a " + dim.replace(/_/g, " ") + " in " + a.symbol + ": scale only, " +
              "no offset");
          }
        }
        if (res.status === "ok") {
          var src = diffRow || ix.units[res.unit], tgt = unitRow(ix, tgtSym, dim);
          if (!tgt || src.base !== tgt.base) {
            p.status = "kept_incompatible_unit";
            p.warnings.push("unit '" + unit + "' (" + src.base + ") cannot be converted to '" + tgtSym + "': values " +
              "kept as they are, original name kept");
          } else {
            var fo = factorOffset(src, tgt), conv = fo[0] !== 1 || fo[1] !== 0;
            p.base_factors = [src.factor, src.offset, tgt.factor, tgt.offset];
            p.variable = v; p.factor = fo[0]; p.offset = fo[1]; p.converted = conv;
            p.unit = tgt.symbol === "_" ? "" : tgt.symbol; p.unit_note = src.note; p.status = conv ? "converted" : "renamed";
            if (res.match === "case-insensitive") p.warnings.push("unit '" + unit + "' read as " + src.symbol + " (case-insensitive match)");
          }
        } else if (res.status === "none" && (dim === "code" || V.unit === "_")) {
          p.variable = v; p.unit = ""; p.status = "renamed";
        } else if (res.status === "none") {
          p.status = "kept_no_unit";
          p.warnings.push("no unit declared: a unit is needed to label it as " + v + " (" + V.unit + "); values " +
            "kept as they are, original name kept");
        } else if (res.status === "unknown") {
          p.status = "kept_unknown_unit";
          p.warnings.push("unit '" + unit + "' is not in the unit table (never guessed): values kept as they are, " +
            "original name kept (it looks like " + v + ")");
        } else if (res.status === "ambiguous") {
          p.status = "kept_ambiguous_unit";
          p.warnings.push("unit '" + unit + "' has several readings in " + dim + ": values kept as they are, original name kept");
        } else {
          var dims = res.dimensions, all = [dim].concat(dims);
          var msg = "declared unit '" + unit + "' is " + dims.join(" or ") + " but " + v + " is " + dim + ": the unit looks mislabelled. " +
            "No documented rule covers it, so values are kept as they are and the channel keeps its name";
          if (all.indexOf("resistivity") >= 0 && all.indexOf("conductivity") >= 0)
            msg += ". Resistivity and conductivity are reciprocal (mS/m = 1000 / ohm.m); OWD never inverts " +
              "values without a documented rule";
          p.status = "kept_unit_mismatch";
          p.warnings.push(msg);
        }
      }
      if (p.variable) {
        var cs = channelStatistic(ix, name, p.description, p.variable);
        p.statistic = cs[0]; p.window = cs[1]; p.statistic_evidence = cs[2];
        p.warnings = p.warnings.concat(cs[3]);
      }
      if (has(t.conflicts, key))
        p.warnings.push("the dictionary records an unresolved conflict for " + key + " (" + t.conflicts[key].join(", ") + "): " +
          "check the values");
      return p;
    });
    var seen = {}, nameStats = namingStatistics(ix, plans);
    plans.forEach(function (p, i) {
      var n = (p.variable === null || names === "original") ? p.original_name : qualifiedName(p.variable, nameStats[i]);
      if (output === "las") { n = lasSafe(n, "CURVE" + (i + 1)); p.unit = lasUnit(p.unit); }
      var base = n, k = 2;
      while (has(seen, n)) { n = base + "_" + k; k++; }
      if (n !== base) p.warnings.push("output name '" + base + "' already used: written as '" + n + "'");
      seen[n] = true; p.name = n;
    });
    return plans;
  }

  // ---------------------------------------------------------------- citation and provenance
  function permalink(ix, names, units, to, digits, csvHeader) {
    var e = encodeURIComponent, nm = (names === "owd" || names === "original") ? names : "custom", u = unitsLabel(units);
    var parts = ["names=" + e(nm), "units=" + e(u === "custom:field" ? "field" : (u === "custom" ? "si" : u))];
    if (units && typeof units === "object") {
      var cu = Object.keys(units).filter(function (k) { return k !== "_default"; }).sort()
        .map(function (k) { return k + ":" + units[k]; }).join(",");
      if (cu) parts.push("u=" + e(cu));
    }
    parts.push("to=" + e(to));
    if (digits !== DEFAULT_DIGITS) parts.push("d=" + (digits || 0));
    if (to === "csv" && csvHeader !== "unit") parts.push("h=" + e(csvHeader));
    parts.push("v=" + e(ix.version));
    return SITE + "/convert/?" + parts.join("&");
  }

  function owdCitation(year) { return "Processed with Open Well Data (Delgado-Uriarte, " + year + "), " + SITE; }
  function owdBibtex(year, version, link) {
    return "@misc{openwelldata" + year + ",\n  author = {Delgado-Uriarte, Daniel},\n" +
      "  title = {Open Well Data: public subsurface data for oil, gas and CCS, with standard names and units},\n" +
      "  year = {" + year + "},\n  howpublished = {\\url{" + SITE + "}},\n" +
      "  note = {Dictionary version " + version + ". Conversion settings: \\url{" + link + "}}\n}";
  }

  function sourceInfo(ix, dataset, citation, licence, url) {
    var AS = "as stated by the source";
    var out = { dataset: dataset || null, name: null, citation: citation || AS, license: licence || AS, url: url || null };
    var d = dataset && ix.t.datasets && has(ix.t.datasets, dataset) ? ix.t.datasets[dataset] : null;
    if (d) { out.name = d.name; out.citation = citation || d.citation; out.license = licence || d.license; out.url = url || d.url; }
    return out;
  }

  function nowUtc(now) { return now || new Date().toISOString().slice(0, 19) + "Z"; }

  var CH_KEYS = ["original_name", "original_unit", "name", "unit", "variable", "candidate_variable", "mapped_by",
    "context_rule", "status", "factor", "offset", "base_factors", "converted", "unit_rule", "unit_note", "warnings", "description",
    "statistic", "window", "statistic_evidence"];

  function provenance(ix, plans, o) {
    var meta = ix.t.meta, when = nowUtc(o.now), year = when.slice(0, 4);
    var digits = o.digits === undefined ? DEFAULT_DIGITS : o.digits;
    var link = permalink(ix, o.names, o.units, o.to, digits, o.csvHeader || "unit");
    var src = o.source || sourceInfo(ix), text = owdCitation(year);
    var extra = o.extraWarnings || [];
    var nw = extra.length;
    plans.forEach(function (p) { nw += p.warnings.length; });
    var custom = {};
    if (o.units && typeof o.units === "object") Object.keys(o.units).forEach(function (k) { if (k !== "_default") custom[k] = o.units[k]; });
    return {
      open_well_data: { engine: "owd.convert", engine_version: meta.engine_version, dictionary_version: meta.dictionary_version,
        dictionary_commit: meta.dictionary_commit, dictionary_date: meta.dictionary_date,
        settings: { names: o.names, units: unitsLabel(o.units), custom_units: custom, to: o.to, digits: digits,
          csv_header: o.csvHeader || "unit", source_format: o.sourceFormat }, permalink: link },
      generated_utc: when,
      input: o.inputInfo || {},
      source: src,
      summary: { channels: plans.length, labelled: plans.filter(function (p) { return p.variable; }).length,
        converted: plans.filter(function (p) { return p.converted; }).length,
        unchanged: plans.filter(function (p) { return !p.converted; }).length,
        not_labelled: plans.filter(function (p) { return !p.variable; }).map(function (p) { return p.original_name; }), warnings: nw },
      warnings: extra.slice(),
      channels: plans.map(function (p) { var c = {}; CH_KEYS.forEach(function (k) { c[k] = p[k]; }); return c; }),
      how_to_cite: { open_well_data: text, full: text + ". Dictionary version " + meta.dictionary_version + "; conversion settings: " + link,
        bibtex: owdBibtex(year, meta.dictionary_version, link), source: src.citation, source_license: src.license },
      license_note: meta.licence_note
    };
  }

  function citationLines(prov) {
    var c = prov.how_to_cite, s = prov.source;
    return [c.open_well_data,
      "Dictionary version " + prov.open_well_data.dictionary_version + "; settings: " + prov.open_well_data.permalink,
      "Source: " + s.citation + ". Licence: " + s.license + ".",
      prov.license_note];
  }

  function channelLine(p) {
    function nu(n, u) { return n + (u ? " [" + u + "]" : ""); }
    var s = nu(p.original_name, p.original_unit) + " -> " + nu(p.name, p.unit);
    if (p.converted) s += " x" + fmtNumber(p.factor) + (p.offset ? " " + (p.offset >= 0 ? "+" : "-") + fmtNumber(Math.abs(p.offset)) : "");
    s += "; " + p.status;
    if (p.mapped_by) s += " (" + p.mapped_by + ")";
    if (p.unit_rule) s += "; rule: " + p.unit_rule.note;
    if (p.unit_note) s += "; unit read as: " + p.unit_note;
    return s;
  }

  // ---------------------------------------------------------------- parsing
  function splitLines(text) { return text.split(/\r\n|\n|\r/); }

  function parseLasLine(line) {
    var dot = line.indexOf(".");
    if (dot < 0) return null;
    var mnem = line.slice(0, dot).trim(), rest = line.slice(dot + 1), unit = rest.match(/^\S*/)[0];
    rest = rest.slice(unit.length);
    var c = rest.lastIndexOf(":");
    return c < 0 ? [mnem, unit, rest.trim(), ""] : [mnem, unit, rest.slice(0, c).trim(), rest.slice(c + 1).trim()];
  }

  function firstItem(items, key) {
    for (var i = 0; i < items.length; i++) if (items[i][0].toUpperCase() === key) return items[i];
    return null;
  }

  function parseLas(ix, text) {
    var sec = null, items = { V: [], W: [], C: [], P: [] }, other = [], data = [];
    splitLines(text).forEach(function (line) {
      var s = line.trim();
      if (s.charAt(0) === "~") { sec = s.slice(1, 2).toUpperCase(); return; }
      if (sec === "A") { if (s && s.charAt(0) !== "#") data.push(s); return; }
      if (sec === "O") { if (s && s.charAt(0) !== "#") other.push(rstrip(line)); return; }
      if (!s || s.charAt(0) === "#" || !has(items, sec)) return;
      var it = parseLasLine(line);
      if (it) items[sec].push(it);
    });
    var vi = firstItem(items.V, "VERS"), vers = vi ? vi[2] : "", vw = vers.split(/\s+/).filter(Boolean);
    var vn = vw.length ? parseNumber(vw[0]) : null;
    if (vn !== null && vn >= 3) throw ConversionError("LAS 3.0 is not supported yet; LAS 1.2 and 2.0 are");
    if (!items.C.length) throw ConversionError("no ~Curve section: not a LAS file");
    var wi = firstItem(items.V, "WRAP"), wrap = (wi ? wi[2] : "NO").trim().toUpperCase().charAt(0) === "Y";
    var ni = firstItem(items.W, "NULL"), nul = ni ? ni[2] : null;
    var n = items.C.length, rows = [], warnings = [], shortN = 0, longN = 0, r, k;
    if (wrap) {
      var toks = [];
      data.forEach(function (ln) { ln.split(/\s+/).forEach(function (x) { if (x) toks.push(x); }); });
      for (k = 0; k < toks.length; k += n) {
        r = toks.slice(k, k + n);
        if (r.length < n) { shortN++; while (r.length < n) r.push(""); }
        rows.push(r);
      }
    } else {
      data.forEach(function (ln) {
        r = ln.split(/\s+/);
        if (r.length < n) { shortN++; while (r.length < n) r.push(""); }
        else if (r.length > n) { longN++; r = r.slice(0, n); }
        rows.push(r);
      });
    }
    if (shortN) warnings.push(shortN + " data rows had fewer values than curves: the missing values are written as null");
    if (longN) warnings.push(longN + " data rows had more values than curves: the extra values were left out");
    var cols = [];
    for (var j = 0; j < n; j++) cols.push(rows.map(function (row) { return row[j]; }));
    var chans = items.C.map(function (c) { return { name: c[0], unit: isNoUnit(ix, c[1]) ? "" : c[1], description: c[3] }; });
    return { format: "LAS", version: vers, channels: chans, columns: cols, null: nul, well: items.W, params: items.P,
      other: other, warnings: warnings, rows: rows.length };
  }

  function csvRows(text, delim) {
    var rows = [], row = [], field = "", q = false, n = text.length;
    for (var i = 0; i < n; i++) {
      var c = text.charAt(i);
      if (q) {
        if (c === '"') { if (i + 1 < n && text.charAt(i + 1) === '"') { field += '"'; i++; } else q = false; }
        else field += c;
      } else if (c === '"') q = true;
      else if (c === delim) { row.push(field); field = ""; }
      else if (c === "\r" || c === "\n") {
        row.push(field); field = ""; rows.push(row); row = [];
        if (c === "\r" && i + 1 < n && text.charAt(i + 1) === "\n") i++;
      } else field += c;
    }
    if (field || row.length) { row.push(field); rows.push(row); }
    return rows;
  }

  function okOrAmb(r) { return r.status === "ok" || r.status === "ambiguous"; }

  function cellUnit(ix, cell) {
    var c = cell.trim(), m = c.match(HDR_UNIT);
    if (m && okOrAmb(resolveUnit(ix, m[2], null))) return m[2].trim();
    return c;
  }

  function parseCsv(ix, text, nul) {
    var lines = splitLines(text), k = 0;
    while (k < lines.length && lines[k].replace(/^\s+/, "").charAt(0) === "#") k++;
    var first = k < lines.length ? lines[k] : "", delim = ",", best = 0;
    [",", ";", "\t"].forEach(function (d) {
      var c = first ? csvRows(first, d)[0].length - 1 : 0;
      if (c > best) { best = c; delim = d; }
    });
    var rows = csvRows(lines.slice(k).join("\n"), delim);
    while (rows.length && rows[rows.length - 1].every(function (c) { return c.trim() === ""; })) rows.pop();
    if (!rows.length) throw ConversionError("empty CSV");
    var chans = rows[0].map(function (c) {
      var m = c.trim().match(HDR_UNIT), name = m ? m[1].trim() : c.trim(), unit = m ? m[2].trim() : "";
      return { name: name, unit: isNoUnit(ix, unit) ? "" : unit, description: c.trim() };
    });
    var start = 1, unitsRow = false;
    if (rows.length > 1) {
      var r2 = rows[1].filter(function (c) { return c.trim(); });
      if (r2.length && !r2.some(function (c) { return parseNumber(c) !== null; })) {
        var known = r2.filter(function (c) { return okOrAmb(resolveUnit(ix, cellUnit(ix, c), null)); }).length;
        if (known >= Math.max(1, Math.floor((r2.length + 1) / 2))) {
          unitsRow = true; start = 2;
          chans.forEach(function (ch, j) {
            if (!ch.unit && j < rows[1].length) { var u = cellUnit(ix, rows[1][j]); ch.unit = isNoUnit(ix, u) ? "" : u; }
          });
        }
      }
    }
    var n = chans.length, data = [], bad = 0;
    rows.slice(start).forEach(function (r) {
      if (r.length !== n) { bad++; r = r.slice(0, n); while (r.length < n) r.push(""); }
      data.push(r);
    });
    var cols = [];
    for (var j = 0; j < n; j++) cols.push(data.map(function (row) { return row[j]; }));
    return { format: "CSV", version: "", channels: chans, columns: cols, null: nul == null ? null : nul, well: [], params: [],
      other: [], warnings: bad ? [bad + " rows had a different number of fields than the header: padded with nulls or cut"] : [],
      rows: data.length, units_row: unitsRow, delimiter: delim };
  }

  // ---------------------------------------------------------------- applying plans
  function convertColumns(tbl, plans, digits, las) {
    var nul = tbl.null, nulNum = nul != null ? parseNumber(nul) : null, nulS = nul != null ? strip(nul) : null;
    return tbl.columns.map(function (col, j) {
      var p = plans[j], conv = p.converted, base = p.base_factors, ntext = 0, n999 = 0, nsp = 0;
      var res = col.map(function (tok) {
        var s = strip(tok);
        if (s === "") return null;
        var x = parseNumber(s);
        if (nul != null && ((nulNum !== null && x !== null && x === nulNum) || s === nulS)) return null;
        if (las && x === null && /\s/.test(s)) { nsp++; s = s.replace(/\s+/g, "_"); }
        if (!conv) return s;
        if (x === null) { ntext++; return s; }
        if (x === -999.25 && nulNum === null) n999++;
        return fmtNumber(applyLinear(x, base), digits);
      });
      if (ntext) p.warnings.push(p.original_name + ": " + ntext + " non-numeric values copied as they are (not converted)");
      if (n999) p.warnings.push(p.original_name + ": the value -999.25 appears " + n999 + " times and was converted as a number; if it " +
        "marks missing data, declare it as the null value");
      if (nsp) p.warnings.push(p.original_name + ": " + nsp + " text values contained spaces; written with '_' because " +
        "LAS has no quoting");
      return res;
    });
  }

  // ---------------------------------------------------------------- writers
  function csvCell(s) {
    if (s === null) return "";
    if (/[,"\n\r]/.test(s) || s !== s.trim()) return '"' + s.replace(/"/g, '""') + '"';
    return s;
  }

  function writeCsv(plans, cols, prov, csvHeader, comments) {
    var lines = [];
    if (comments) citationLines(prov).forEach(function (l) { lines.push("# " + l); });
    lines.push(plans.map(function (p) { return csvCell(csvHeader === "plain" || !p.unit ? p.name : p.name + " [" + p.unit + "]"); }).join(","));
    var n = cols.length ? cols[0].length : 0;
    for (var i = 0; i < n; i++) lines.push(cols.map(function (c) { return csvCell(c[i]); }).join(","));
    return lines.join("\n") + "\n";
  }

  function lasItems(items) {
    if (!items.length) return [];
    var left = items.map(function (i) { return i[0] + "." + i[1]; });
    var w = Math.max.apply(null, left.map(function (x) { return x.length; }));
    var vw = Math.max.apply(null, items.map(function (i) { return i[2].length; }));
    return items.map(function (it, i) { return rstrip(" " + left[i].padEnd(w) + " " + it[2].padEnd(vw) + " : " + it[3]); });
  }

  var WELL_DEFAULT = [["COMP", "COMPANY"], ["WELL", "WELL"], ["FLD", "FIELD"], ["LOC", "LOCATION"], ["SRVC", "SERVICE COMPANY"],
    ["DATE", "LOG DATE"], ["UWI", "UNIQUE WELL ID"]];

  function writeLas(tbl, plans, cols, prov, digits) {
    var nullOut = strip(tbl.null || "") || "-999.25", p0 = plans[0], iu = p0.unit, col0 = cols[0], i;
    var strt = "", stop = "";
    for (i = 0; i < col0.length; i++) if (col0[i] !== null) { strt = col0[i]; break; }
    for (i = col0.length - 1; i >= 0; i--) if (col0[i] !== null) { stop = col0[i]; break; }
    var si = tbl.format === "LAS" ? firstItem(tbl.well, "STEP") : null, srcStep = si ? si[2] : null, step;
    if (srcStep !== null && !p0.converted) step = srcStep;
    else if (srcStep !== null && parseNumber(srcStep) !== null) step = fmtNumber(parseNumber(srcStep) * p0.base_factors[0] / p0.base_factors[2], digits);
    else {
      var nums = col0.filter(function (v) { return v !== null; }).map(parseNumber).filter(function (x) { return x !== null; });
      step = "0";
      if (nums.length > 1) {
        var d0 = nums[1] - nums[0], ok = d0 !== 0;
        for (i = 2; ok && i < nums.length; i++) if (!(Math.abs((nums[i] - nums[i - 1]) - d0) <= 1e-9 * Math.abs(d0))) ok = false;
        if (ok) step = fmtNumber(d0, 10);
      }
    }
    var fixed = { STRT: [iu, strt, "START DEPTH"], STOP: [iu, stop, "STOP DEPTH"], STEP: [iu, step, "STEP"], NULL: ["", nullOut, "NULL VALUE"] };
    var well = ["STRT", "STOP", "STEP", "NULL"].map(function (k) {
      var old = firstItem(tbl.well, k), f = fixed[k];
      return [k, f[0], f[1], old && old[3] ? old[3] : f[2]];
    });
    if (tbl.format === "LAS") tbl.well.forEach(function (it) { if (!has(fixed, it[0].toUpperCase())) well.push(it.slice()); });
    else WELL_DEFAULT.forEach(function (w) { well.push([w[0], "", "", w[1]]); });
    var curves = plans.map(function (p) {
      var d = tbl.format === "LAS" ? p.description : "";
      if (p.name !== p.original_name || p.converted || p.unit !== p.original_unit) {
        var was = "was " + p.original_name + (p.original_unit ? " [" + p.original_unit + "]" : "");
        d = d ? d + " | " + was : was;
      }
      return [p.name, p.unit, "", d];
    });
    var o = prov.open_well_data;
    var params = tbl.params.filter(function (it) { return it[0].toUpperCase().indexOf("OWD_") !== 0; }).map(function (it) { return it.slice(); });
    params.push(["OWD_DICT", "", o.dictionary_version, "Open Well Data dictionary version"],
      ["OWD_ENGINE", "", o.engine_version, "Open Well Data conversion engine version"],
      ["OWD_DATE", "", prov.generated_utc, "Converted on (UTC)"],
      ["OWD_NAMES", "", o.settings.names, "Naming scheme"],
      ["OWD_UNITS", "", o.settings.units, "Unit target"],
      ["OWD_LINK", "", o.permalink, "Conversion settings (no data in the link)"]);
    var other = citationLines(prov);
    other.push("Channels (original [unit] -> output [unit], factor, offset; status (how mapped); rule):");
    plans.forEach(function (p) { other.push("  " + channelLine(p)); });
    var ws = prov.warnings.slice();
    plans.forEach(function (p) { p.warnings.forEach(function (w) { ws.push(p.original_name + ": " + w); }); });
    if (ws.length) { other.push("Warnings:"); ws.forEach(function (w) { other.push("  " + w); }); }
    other.push("BibTeX:");
    other = other.concat(prov.how_to_cite.bibtex.split("\n"));
    if (tbl.other.length) { other.push("Original ~Other section:"); other = other.concat(tbl.other); }
    other = other.map(function (l) { return l.replace(/^\s+/, "").charAt(0) === "~" ? " " + l : l; });
    var out = ["~Version Information"].concat(lasItems([["VERS", "", "2.0", "CWLS log ASCII Standard - Version 2.0"],
      ["WRAP", "", "NO", "One line per depth step"]]));
    out.push("~Well Information"); out = out.concat(lasItems(well));
    out.push("~Curve Information"); out = out.concat(lasItems(curves));
    out.push("~Parameter Information"); out = out.concat(lasItems(params));
    out.push("~Other Information"); out = out.concat(other);
    out.push("~A");
    var strs = cols.map(function (c) { return c.map(function (v) { return v === null ? nullOut : v; }); });
    var widths = strs.map(function (c) { var w = 1; c.forEach(function (x) { if (x.length > w) w = x.length; }); return w; });
    var n = cols.length ? cols[0].length : 0;
    for (i = 0; i < n; i++) {
      var line = [];
      for (var j = 0; j < strs.length; j++) line.push(strs[j][i].padStart(widths[j]));
      out.push(line.join(" "));
    }
    return out.join("\n") + "\n";
  }

  // ---------------------------------------------------------------- top level
  function inputInfo(tbl, fileName, sha) {
    var vw = tbl.version.split(/\s+/).filter(Boolean);
    var info = { file: fileName || "", format: tbl.format === "LAS" && vw.length ? "LAS " + vw[0] : tbl.format,
      sha256: sha || null, rows: tbl.rows, null: tbl.null == null ? null : tbl.null };
    if (tbl.format === "LAS") {
      var w = {};
      tbl.well.forEach(function (i) { if (["WELL", "COMP", "FLD", "UWI", "API", "SRVC", "CTRY", "DATE"].indexOf(i[0].toUpperCase()) >= 0 && i[2]) w[i[0]] = i[2]; });
      info.well = w;
    }
    return info;
  }

  function parseText(ix, text, kind, nul) {
    text = String(text).replace(/^﻿+/, "");
    if (!kind) kind = /^\s*~/.test(text) ? "las" : "csv";
    var tbl = kind === "las" ? parseLas(ix, text) : parseCsv(ix, text, nul);
    if (kind === "las" && nul != null) tbl.null = nul;
    return tbl;
  }

  // opts: names, units, to ('csv'|'las'), sourceFormat, null, digits, csvHeader, comments, source, fileName, inputSha256, now
  function convertText(ix, text, opts) {
    opts = opts || {};
    var to = opts.to || "csv", names = opts.names || "owd", units = opts.units || "si";
    var digits = opts.digits === undefined ? DEFAULT_DIGITS : opts.digits, csvHeader = opts.csvHeader || "unit";
    if (to !== "csv" && to !== "las") throw ConversionError("the browser writes csv or las");
    var tbl = parseText(ix, text, opts.kind, opts.null);
    var fmt = opts.sourceFormat || (ix.t.log_formats.indexOf(tbl.format) >= 0 ? tbl.format : "table");
    var plans = planChannels(ix, tbl.channels, names, units, fmt, to === "las" ? "las" : null,
      opts.source && opts.source.dataset ? opts.source.dataset : null);
    var cols = convertColumns(tbl, plans, digits, to === "las");
    var prov = provenance(ix, plans, { names: names, units: units, to: to, source: opts.source || sourceInfo(ix),
      inputInfo: inputInfo(tbl, opts.fileName, opts.inputSha256), now: opts.now, digits: digits, csvHeader: csvHeader,
      sourceFormat: fmt, extraWarnings: tbl.warnings });
    var out = to === "csv" ? writeCsv(plans, cols, prov, csvHeader, opts.comments) : writeLas(tbl, plans, cols, prov, digits);
    return { text: out, provenance: prov, plans: plans, table: tbl };
  }

  function provenanceJson(prov) { return JSON.stringify(prov, null, 1) + "\n"; }

  // ---------------------------------------------------------------- getting data (routes for the "Get data" button)
  // copy: our standardized copy (CORS-enabled host, e.g. Zenodo) -> fetched and converted here.
  // helper: `owd helper` running on this computer -> it downloads from the source, the browser converts.
  // direct: a recipe file that is LAS/CSV on a host that allows CORS -> fetched here; on failure, guided.
  // guided: download it from the source (its page opens in a new tab), then drop it here. Never accepts terms for the user.
  function getDataPlan(t, id, env) {
    env = env || {};
    var d = t.datasets && has(t.datasets, id) ? t.datasets[id] : null;
    if (!d) return { route: "guided", reason: "unknown dataset", source: null };
    var base = env.copiesBase != null ? env.copiesBase : (t.copies_base_url || "");
    var guided = { route: "guided", source: d.url, terms: d.terms || null, files: d.files || [] };
    if (d.policy === "copy" && base) return { route: "copy", index: base.replace(/\/$/, "") + "/" + id + "/index.json", fallback: guided };
    if (env.helper && d.download === "auto") return { route: "helper", dataset: id, fallback: guided };
    var direct = (d.files || []).filter(function (f) { return /\.(las|csv|txt)$/i.test(f.name) && f.url; });
    if (d.download === "auto" && direct.length) return { route: "direct", files: direct, fallback: guided };
    return guided;
  }

  function api(tables) {
    var ix = new Index(tables);
    return {
      tables: tables, index: ix, version: ix.version,
      convertText: function (text, opts) { return convertText(ix, text, opts); },
      planChannels: function (ch, names, units, fmt, output, dataset) { return planChannels(ix, ch, names, units, fmt, output, dataset); },
      channelStatistic: function (name, description, v) { return channelStatistic(ix, name, description, v); },
      parseText: function (text, kind, nul) { return parseText(ix, text, kind, nul); },
      resolveUnit: function (s, dim) { return resolveUnit(ix, s, dim); },
      unitsOf: function (dim, base) { return unitsOf(ix, dim, base); },
      unitRow: function (s, dim) { return unitRow(ix, s, dim); },
      targetUnit: function (v, units) { return targetUnit(ix, v, units); },
      permalink: function (names, units, to, digits, h) { return permalink(ix, names, units, to, digits === undefined ? DEFAULT_DIGITS : digits, h || "unit"); },
      sourceInfo: function (d, c, l, u) { return sourceInfo(ix, d, c, l, u); },
      cite: function (names, units, to, digits, h, now) {
        var year = nowUtc(now).slice(0, 4), link = permalink(ix, names, units, to, digits === undefined ? DEFAULT_DIGITS : digits, h || "unit");
        var text = owdCitation(year);
        return { open_well_data: text, full: text + ". Dictionary version " + ix.version + "; conversion settings: " + link,
          bibtex: owdBibtex(year, ix.version, link) };
      },
      getDataPlan: function (id, env) { return getDataPlan(tables, id, env); }
    };
  }

  var OWDConvert = { create: api, fmtNumber: fmtNumber, parseNumber: parseNumber, applyLinear: applyLinear,
    provenanceJson: provenanceJson, getDataPlan: getDataPlan, DEFAULT_DIGITS: DEFAULT_DIGITS, SITE: SITE };
  if (typeof module === "object" && module.exports) module.exports = OWDConvert;
  else root.OWDConvert = OWDConvert;
})(typeof self !== "undefined" ? self : this);
