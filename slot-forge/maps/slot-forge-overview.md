# MAP:slot-forge 總覽(v0.1)

```
demo 網址
  │
  ▼
[slot-rules-ingest] ──► rules.json ──┬──► [slot-scaffold](T1) ──► 新專案骨架(core/game/bundle)
   (T2-a,草稿)                       ├──► [slot-flow-gen](T2-b) ──► 狀態機 TS
                                     ├──► [slot-reel](T4) ──► reel 元件設定
                                     ├──► [slot-mock-server](T9) ──► 假後端(spin 協議)
                                     └──► [slot-ui-gen](T3) ◄── mockup
                                                │
                                                ▼
                                   Cocos 3.7.3 開啟 → 假登入 → Spin 一次(最小閉環)
                                                │
                                                ▼
                                  T5 美術 / T6 節奏 / T7 Spine / T8 數學 / T10–T15
```

| 節點 | 軌道 | 狀態 | 依賴 |
|------|------|------|------|
| slot-rules-ingest | T2-a | 草稿 skill(schema+validator 可跑) | demo HTML |
| slot-flow-gen | T2-b | 未開始 | 1070s refs(事件命名) |
| slot-scaffold | T1 | 未開始 | 1070s refs |
| slot-reel | T4 | 未開始 | 1070s / 1048s / 1061s refs |
| slot-ui-gen | T3 | 未開始 | mockup-layout |
| slot-mock-server | T9 | 未開始 | spin 協議 schema(可先做) |
| slot-forge(總入口) | — | 未開始 | 以上全部 |
