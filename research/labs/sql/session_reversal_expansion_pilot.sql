-- AURELIA Candidate C exploratory session-reversal / next-session-range event study
-- Run date: 2026-10-10
-- Input: temporary Massive workspace table mnqh5_q1_2025, 5-minute OHLC for MNQH5.
-- NOT a broker backtest. No bid/ask, transaction-cost, order/fill, or P&L model.
-- Recreate the authorized source table before running; raw bars were not stored in AURELIA.
-- Session definitions use America/New_York; the supplied table window ends in Q1 2025,
-- so only the spring 2025 DST boundary is included.
WITH b AS (
 SELECT *,datetime(window_start/1000000000,'unixepoch',
  CASE WHEN datetime(window_start/1000000000,'unixepoch')>='2025-03-09 07:00:00' THEN '-4 hours' ELSE '-5 hours' END) et
 FROM mnqh5_q1_2025
), x AS (
 SELECT *,
  CASE WHEN time(et)>='18:00:00' THEN date(et,'+1 day') ELSE date(et) END sd,
  CASE WHEN time(et)>='18:00:00' OR time(et)<'02:00:00' THEN 'OVERNIGHT'
       WHEN time(et)>='02:00:00' AND time(et)<'09:30:00' THEN 'EUROPE'
       WHEN time(et)>='09:30:00' AND time(et)<'17:00:00' THEN 'US_DAY' END sn
 FROM b
), sb AS (SELECT * FROM x WHERE sn IS NOT NULL),
s0 AS (
 SELECT sd,sn,MIN(window_start) first_ns,MAX(window_start) last_ns,MIN(et) fst,MAX(et) lst,COUNT(*) n,MAX(high) hi,MIN(low) lo
 FROM sb GROUP BY sd,sn
), s AS (
 SELECT *,hi-lo rng,sn||'|'||sd sid,
 CASE WHEN sn='OVERNIGHT' AND n=96 AND fst=date(sd,'-1 day')||' 18:00:00' AND lst=sd||' 01:55:00' THEN 1
      WHEN sn='EUROPE' AND n=90 AND fst=sd||' 02:00:00' AND lst=sd||' 09:25:00' THEN 1
      WHEN sn='US_DAY' AND n=90 AND fst=sd||' 09:30:00' AND lst=sd||' 16:55:00' THEN 1 ELSE 0 END complete
 FROM s0
), hr AS (
 SELECT c.sid,c.sn,c.sd,h.rng,ROW_NUMBER() OVER(PARTITION BY c.sid ORDER BY h.first_ns DESC) rec
 FROM s c JOIN s h ON h.sn=c.sn AND h.complete=1 AND h.first_ns<c.first_ns WHERE c.complete=1
), ho AS (
 SELECT *,ROW_NUMBER() OVER(PARTITION BY sid ORDER BY rng) vr,COUNT(*) OVER(PARTITION BY sid) cnt FROM hr WHERE rec<=20
), med AS (
 SELECT sid,AVG(CASE WHEN vr IN ((cnt+1)/2,(cnt+2)/2) THEN rng END) med,MAX(cnt) cnt FROM ho GROUP BY sid
), ctx AS (
 SELECT c.*,p.hi ph,p.lo pl,n.sid next_sid,n.sn next_sn,n.rng next_rng,m.med next_median,m.cnt next_history_count
 FROM s c
 JOIN s p ON p.sd=CASE WHEN c.sn='OVERNIGHT' THEN date(c.sd,'-1 day') ELSE c.sd END
  AND p.sn=CASE WHEN c.sn='OVERNIGHT' THEN 'US_DAY' WHEN c.sn='EUROPE' THEN 'OVERNIGHT' ELSE 'EUROPE' END
 JOIN s n ON n.sn=CASE WHEN c.sn='OVERNIGHT' THEN 'EUROPE' WHEN c.sn='EUROPE' THEN 'US_DAY' ELSE 'OVERNIGHT' END
  AND n.sd=CASE WHEN c.sn='US_DAY' THEN date(c.sd,'+1 day') ELSE c.sd END
 JOIN med m ON m.sid=n.sid AND m.cnt=20
 WHERE c.complete=1 AND p.complete=1 AND n.complete=1
), sig0 AS (
 SELECT sb.sd,sb.sn,sb.window_start,c.sid,
 CASE WHEN sb.low<=c.pl-0.25 AND sb.close>c.pl AND sb.high>=c.ph+0.25 AND sb.close<c.ph THEN 'AMBIGUOUS'
      WHEN sb.low<=c.pl-0.25 AND sb.close>c.pl THEN 'LONG'
      WHEN sb.high>=c.ph+0.25 AND sb.close<c.ph THEN 'SHORT' END sig
 FROM sb JOIN ctx c ON c.sid=sb.sn||'|'||sb.sd
), sig AS (
 SELECT *,ROW_NUMBER() OVER(PARTITION BY sid ORDER BY window_start) rn FROM sig0 WHERE sig IS NOT NULL
), first_sig AS (SELECT * FROM sig WHERE rn=1), joined AS (
 SELECT c.sn,c.sd,c.sid,c.next_median,c.next_rng,f.sig,
 CASE WHEN c.next_rng>c.next_median THEN 1.0 ELSE 0.0 END expanded,
 CASE WHEN f.sig IN ('LONG','SHORT') THEN c.next_rng/c.next_median END ratio
 FROM ctx c LEFT JOIN first_sig f ON f.sid=c.sid
), r AS (
 SELECT sn,substr(sd,1,4) yr,COUNT(*) transitions,SUM(CASE WHEN sig IS NOT NULL THEN 1 ELSE 0 END) signal_sessions,
 SUM(CASE WHEN sig='LONG' THEN 1 ELSE 0 END) long_signals,
 SUM(CASE WHEN sig='SHORT' THEN 1 ELSE 0 END) short_signals,
 SUM(CASE WHEN sig='AMBIGUOUS' THEN 1 ELSE 0 END) ambiguous_signals,
 AVG(expanded) baseline_next_session_expansion_rate,
 AVG(CASE WHEN sig IN ('LONG','SHORT') THEN expanded END) expansion_rate_after_signal,
 AVG(ratio) mean_expansion_ratio_after_signal
 FROM joined GROUP BY sn,substr(sd,1,4)
)
SELECT * FROM r ORDER BY sn;
