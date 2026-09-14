# Database-aware non-POS challenge questions

2026-09-14. Agent-authored from existing fictional databases; not a user holdout.
Twenty-four questions (20 answerable, four refusal controls), with independent
SQL and distinguishing wrong-query controls validated before any planner call.
See [validation notes](db-aware-challenge-01.md). Wording is new relative to the
tracked case files, but semantic families intentionally reuse known risks.

## Service operations

Datasource: `service_test`; as_of: 2026-04-15 12:00 Asia/Taipei.

工時紀錄共有幾筆？其中有填寫工時分鐘數的紀錄有幾筆？零分鐘也算有填寫。

How many distinct tickets have at least one work log? Count each ticket once, even if it has several logs.

實際登錄的工時總共多少分鐘？不要把工單的預估分鐘數加進去，也不要因此排除有預估值的工單。

作業ログがまだないチケットも含めて、全チケットの件数と見積作業時間の合計を示してください。

What is the total logged time across all work logs, including entries whose work date is unknown?

作業日時が未記録のログだけを対象に、作業時間の合計を分単位で示してください。

按實際作業日期，列出2026年1月至3月每月的登錄工時總分鐘數；沒有作業日期的紀錄不要歸入任何月份。

What is the average number of minutes per work log with a recorded minutes value? Include zero-minute logs; exclude missing minutes from the average.

2026年2月完全沒有工時紀錄的專案有幾個？尚未有任何工單的專案也要計入。

依實際結案時間計算，2026年2月結案的工單有幾張？不要按建立時間篩選。

有結案時間的工單佔全部工單的比例是多少？分母包含建立時間未知的工單。

列出登錄工時總量超過200分鐘的團隊，顯示總分鐘數與佔全部團隊工時的比例；分母仍包含未超過200分鐘的團隊，沒有作業日期的工時也算入總量。

What percentage of tickets breached their contractual SLA?

有建立時間與結案時間的工單，從建立到結案平均經過多少小時？

## IoT operations

Datasource: `iot_spike`; as_of: 2026-08-15 12:00 Asia/Taipei.

For alerts raised in July 2026, return the number of alert records and the number of distinct devices that raised them.

台北時間2026年8月1日至8月14日（含）處理完成的告警有幾筆？依 resolved_at 計算，不論告警是哪一天發生的。

resolved_at が未記録のアラートは何件ありますか？重大度にかかわらず数えてください。

不論設備目前是線上、離線或維護中，全部設備的每月訂閱費合計是多少？

Among alerts with a non-NULL downtime_minutes value, what is the average downtime in minutes?

critical 告警佔全部告警紀錄的比例是多少？分母包括沒有停機分鐘數的告警。

What is the total monthly subscription fee for devices at each site? Count each device once, regardless of how many telemetry readings it has.

2026年7月に critical のアラートを一度も発生させなかったデバイスは何台ですか？8月のアラートは判定に含めないでください。

所有租賃設備的每月訂閱費合計是多少？

全テレメトリ記録の温度の中央値は何度ですか？
