; SMT2 file generated from compliance case automatic
; Case ID: case_0
; Generated at: 2025-12-06T23:34:02.958657
;
; This file can be executed with Z3:
;   z3 case_0.smt2
;

(set-logic ALL)

; ============================================================
; Variable Declarations
; ============================================================

(declare-const capital_adequate Bool)
(declare-const capital_insufficient Bool)
(declare-const capital_insufficient_plan_executed Bool)
(declare-const capital_insufficient_plan_submitted Bool)
(declare-const capital_level Int)
(declare-const capital_severely_insufficient Bool)
(declare-const capital_significantly_insufficient Bool)
(declare-const level_2_measures_executed Bool)
(declare-const level_3_measures_done Bool)
(declare-const level_3_measures_executed Bool)
(declare-const level_4_measures_done Bool)
(declare-const level_4_measures_executed Bool)
(declare-const net_worth Real)
(declare-const net_worth_ratio_prev1 Real)
(declare-const net_worth_ratio_prev2 Real)
(declare-const own_capital Real)
(declare-const penalty Bool)
(declare-const risk_capital Real)

; ============================================================
; Constraints (Legal Rules)
; ============================================================

; [insurance:capital_level] 保險業資本等級分類（1=資本適足, 2=資本不足, 3=資本顯著不足, 4=資本嚴重不足）
(assert (let ((a!1 (or (not (<= (/ 1.0 2.0) (/ own_capital risk_capital)))
               (not (<= 0.0 net_worth))))
      (a!2 (or (and (not (<= (/ 1.0 50.0) net_worth_ratio_prev1))
                    (not (<= (/ 1.0 50.0) net_worth_ratio_prev2)))
               (and (<= 0.0 net_worth_ratio_prev1)
                    (not (<= (/ 1.0 50.0) net_worth_ratio_prev1))
                    (not (<= (/ 3.0 100.0) net_worth_ratio_prev2)))))
      (a!4 (or (and (<= (/ 1.0 50.0) net_worth_ratio_prev1)
                    (not (<= (/ 3.0 100.0) net_worth_ratio_prev1))
                    (<= (/ 3.0 100.0) net_worth_ratio_prev2))
               (and (<= (/ 3.0 100.0) net_worth_ratio_prev1)
                    (<= (/ 3.0 100.0) net_worth_ratio_prev2)))))
(let ((a!3 (and (<= (/ 1.0 2.0) (/ own_capital risk_capital))
                (not (<= (/ 3.0 2.0) (/ own_capital risk_capital)))
                a!2))
      (a!5 (and (<= (/ 1.0 2.0) (/ own_capital risk_capital))
                (not (<= 2.0 (/ own_capital risk_capital)))
                a!4)))
  (= (to_real capital_level) (ite a!1 4.0 (ite a!3 3.0 (ite a!5 2.0 0.0)))))))

; [insurance:capital_adequate] 資本適足：資本適足率≥200%且最近二期淨值比率至少一期≥3%
(assert (= capital_adequate
   (and (>= (/ own_capital risk_capital) 2.0)
        (or (<= 3.0 net_worth_ratio_prev1) (<= 3.0 net_worth_ratio_prev2)))))

; [insurance:capital_insufficient] 資本不足：資本適足率在150%以上未達200%或最近二期淨值比率均未達3%且至少一期在2%以上
(assert (let ((a!1 (and (>= (/ own_capital risk_capital) (/ 3.0 2.0))
                (not (>= (/ own_capital risk_capital) 2.0)))))
(let ((a!2 (or a!1
               (and (not (<= 3.0 net_worth_ratio_prev1))
                    (not (<= 3.0 net_worth_ratio_prev2))
                    (or (<= 2.0 net_worth_ratio_prev1)
                        (<= 2.0 net_worth_ratio_prev2))))))
  (= capital_insufficient a!2))))

; [insurance:capital_significantly_insufficient] 資本顯著不足：資本適足率在50%以上未達150%或最近二期淨值比率均未達2%且淨值比率均≥0
(assert (let ((a!1 (and (>= (/ own_capital risk_capital) (/ 1.0 2.0))
                (not (>= (/ own_capital risk_capital) (/ 3.0 2.0))))))
(let ((a!2 (or a!1
               (and (not (<= 2.0 net_worth_ratio_prev1))
                    (not (<= 2.0 net_worth_ratio_prev2))
                    (<= 0.0 net_worth_ratio_prev1)
                    (<= 0.0 net_worth_ratio_prev2)))))
  (= capital_significantly_insufficient a!2))))

; [insurance:capital_severely_insufficient] 資本嚴重不足：資本適足率低於50%或淨值低於0
(assert (let ((a!1 (or (not (>= (/ own_capital risk_capital) (/ 1.0 2.0)))
               (not (<= 0.0 net_worth)))))
  (= capital_severely_insufficient a!1)))

; [insurance:capital_level_consistency] 資本等級依低等級原則決定
(assert (let ((a!1 (ite capital_severely_insufficient
                4
                (ite capital_significantly_insufficient
                     3
                     (ite capital_insufficient 2 (ite capital_adequate 1 0))))))
  (= capital_level a!1)))

; [insurance:level_4_measures_executed] 資本嚴重不足等級措施已執行
(assert (= level_4_measures_executed level_4_measures_done))

; [insurance:level_3_measures_executed] 資本顯著不足等級措施已執行
(assert (= level_3_measures_executed level_3_measures_done))

; [insurance:level_2_measures_executed] 資本不足等級措施已執行（提出增資或改善計畫且確實執行）
(assert (= level_2_measures_executed
   (and capital_insufficient_plan_submitted capital_insufficient_plan_executed)))

; [meta:penalty_default_false] 預設不處罰
(assert (not penalty))

; [meta:penalty_conditions] 處罰條件：資本不足等級達一定程度且未執行對應措施時處罰
(assert (= penalty
   (or (and (= 3 capital_level) (not level_3_measures_executed))
       (and (= 4 capital_level) (not level_4_measures_executed))
       (and (= 2 capital_level) (not level_2_measures_executed)))))

; ============================================================
; Facts (Case Specific)
; ============================================================

(assert (= own_capital (/ 11109.0 10000.0)))
(assert (= risk_capital 1.0))
(assert (= net_worth (/ 297.0 100.0)))
(assert (= net_worth_ratio_prev1 (/ 297.0 100.0)))
(assert (= net_worth_ratio_prev2 (/ 297.0 100.0)))
(assert (= capital_insufficient_plan_submitted true))
(assert (= capital_insufficient_plan_executed false))
(assert (= level_2_measures_executed false))
(assert (= level_3_measures_done false))
(assert (= level_4_measures_done false))
(assert (= penalty true))

; ============================================================
; Check Satisfiability
; ============================================================

(check-sat)
(get-model)

; ============================================================
; Additional Information
; ============================================================
; Total constraints: 11
; Total variables: 18
; Total facts: 11
;
; Expected result:
;   - If UNSAT: Case violates legal rules
;   - If SAT: Case complies with legal rules (or error in constraints)
