#set text(font: "Kai")
#set heading(numbering: "1.1")



= MPC 优化问题

== 最小化:

$
  sum(||x_k - x_"ref"||^2_Q + ||u_k||^2_R)
$

== 约束:

$
  x_(k+1) = A x_k + B u_k, "while:" abs(u_k) <= attach("stick", br: "max")
$


= 延迟补偿

测量状态 $arrow.r$ 前向预测 $arrow.r$ 当前真实状态

$
  x_"real" = x_"measured" + sum A^i B u_(k-"delay"+i)
$


= 系统辨识

== 数据
$
  [x(k),u(k-"delay")] arrow.r x(k+1)
$
== 模型
$
  x(k+1) = A x(k) + B u(k-"delay")
$
== 求解
$
  theta = [A; B] = (X^T X)^(-1) X^T Y
$
