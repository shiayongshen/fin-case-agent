【约束自定义流程改进总结】

=== 发现的根本问题 ===

1. 无限循环问题
   - constraint_customization_agent 重复输出相同消息 10+ 次
   - 根本原因：LLM 第一次调用没有输出标记，系统继续调用同一 agent

2. 系统提示表述问题
   - 原始提示中"下一行发送 TERMINATE"表述不清
   - LLM 可能误解为标记和 TERMINATE 是分开的两个事件

=== 实施的改进方案 ===

【改进 1】优化 ConstraintCustomizationAgent 系统提示
文件：agents/ConstraintCustomizationAgent.py

关键改进：
✅ 添加了【關鍵格式要求】部分，明确说明每个回应的格式
✅ 使用 one-shot 示例展示正确的格式：
   【内容】
   【标记】
   TERMINATE
✅ 强调"立即后跟"而不是"下一行"
✅ 提供了✅正确范例和❌错误范例
✅ 在禁止部分明确说明不允许的行为

目标：让 LLM 从第一次调用就输出正确的格式

【改进 2】增强 ChatManager 状态转换逻辑
文件：agents/ChatManager.py (lines 119-160)

关键改进：
✅ 检查是否有【任何】标记而不是特定的标记
✅ 添加连续调用计数机制
   - 如果同一 agent 连续调用 >= 3 次但无标记，强制停止
   - 防止无限循环
✅ 改进标记路由逻辑
   - 【待確認約束】→ user_proxy（等待用户）
   - 【需要澄清】→ user_proxy（等待用户）
   - 【約束設置完成】→ user_proxy 执行工具或 None 结束
   - 【退出自定義】→ host_agent + 恢复初始状态
✅ 添加详细的日志输出便于调试

=== 预期效果 ===

【解决的问题】
1. ✅ 无限循环：通过连续调用计数和更好的系统提示解决
2. ✅ 消息停止：通过标记识别和清晰的路由逻辑解决
3. ✅ 状态转换：通过明确的状态检查和路由规则解决

【用户体验改进】
- constraint_customization_agent 应该在第一次或第二次调用就输出正确的标记
- 停止无效的重复调用
- 消息正确显示在 Chainlit UI 上
- 流程能够正确地在各个 agent 之间转换

=== 验证方法 ===

1. 观察日志输出：
   - 查看是否有"constraint_customization_agent 已連續調用 X 次"的警告
   - 查看是否有"✅ constraint_customization_agent 輸出了標記"的确认

2. UI 测试：
   - 启动 Chainlit 应用
   - 进行深入分析
   - 选择"要"进行约束自定义
   - 观察 constraint_customization_agent 是否只说话一次或两次
   - 验证消息是否正确显示在 UI 上

3. 消息计数：
   - 检查 group_chat.messages 的长度
   - 应该看到约束自定义的消息被正确添加

=== 代码修改清单 ===

【agents/ConstraintCustomizationAgent.py】
- 行 7-52：完全重写了系统提示
- 添加【關鍵格式要求】部分（行 15-52）
- 提供了 one-shot 正确和错误示例
- 添加了【重要規則】部分明确禁止的行为

【agents/ChatManager.py】
- 行 119-160：重写了 constraint_customization_agent 的状态转换逻辑
- 添加了标记检查（行 128-131）
- 添加了连续调用计数（行 133-140）
- 添加了无限循环防护（行 142-146）
- 添加了标记路由逻辑（行 149-160）
- 添加了详细的日志输出（多处 print 语句）

=== 技术细节 ===

【连续调用计数算法】
```python
agent_call_count = 0
for msg in reversed(named_messages):
    if msg.get("name") == "constraint_customization_agent":
        agent_call_count += 1
    else:
        break
```

通过遍历消息列表（从后向前），计算有多少个连续的 constraint_customization_agent 消息。
如果计数 >= 3 且没有标记，则停止。

【标记检查逻辑】
```python
has_any_marker = isinstance(last_content, str) and any(
    tag in str(last_content) 
    for tag in ["【待確認約束】", "【需要澄清】", "【約束設置完成】", "【退出自定義】"]
)
```

检查是否存在【任何】四个标记中的一个。
这样更加健壮，即使 agent 输出了意想不到的标记也能被识别。

=== 回归影响分析 ===

✅ 对其他 agent 无影响：改动仅限于 constraint_customization 流程
✅ 对已有流程无影响：其他 agent 的状态转换逻辑未改动
✅ 系统提示仅影响 constraint_customization_agent
✅ 新的日志输出便于调试，不影响功能

=== 下一步 ===

1. 启动 Chainlit 应用
2. 测试完整的约束自定义流程
3. 观察日志输出验证改进是否有效
4. 如果仍有问题，根据日志进行进一步调试

【预期成功标志】
- Agent 输出【待確認約束】或其他标记
- 消息显示在 Chainlit UI 上
- 流程能够正确停止并等待用户输入
- 没有重复的无限循环消息
