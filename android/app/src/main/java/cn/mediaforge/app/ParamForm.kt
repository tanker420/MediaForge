package cn.mediaforge.app

import android.content.Context
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.widget.ArrayAdapter
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.SeekBar
import android.widget.Spinner
import android.widget.TextView
import androidx.core.content.ContextCompat
import com.google.android.material.color.MaterialColors
import kotlin.math.roundToInt

/**
 * 依据 Formats.Param 目录自动生成参数编辑控件（桌面版 widgets.ParamForm 的移植）。
 *
 * v1.3.0：
 * - 两级布局：tier=basic 常用项直接展示，其余收进默认折叠的「高级设置」；
 * - 有取值范围的数值参数用「滑块 + 输入框 + 固定单位」联动控件；
 * - 防呆：失焦/取值时自动 clamp 到 [min, max]，非法输入回退默认值；
 *   单位是独立静态文本，手动输入只改数值、不改单位。
 */
class ParamForm @JvmOverloads constructor(
    context: Context, attrs: android.util.AttributeSet? = null,
) : LinearLayout(context, attrs) {

    private val controls = LinkedHashMap<String, View>()
    private val sliders = LinkedHashMap<String, SliderRow>()
    private val params = mutableListOf<Param>()
    private var advToggle: TextView? = null
    private var advContainer: LinearLayout? = null

    /** 滑块联动行：SeekBar 与输入框双向同步，单位为固定后缀。 */
    private inner class SliderRow(val p: Param, val seek: SeekBar, val edit: EditText) {
        val lo = p.min ?: 0.0
        val hi = if ((p.max ?: 100.0) > lo) p.max!! else lo + 1.0
        val step = if (p.step > 0.0) p.step else 1.0

        init {
            seek.max = maxOf(1, ((hi - lo) / step).roundToInt())
            seek.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(s: SeekBar?, progress: Int, fromUser: Boolean) {
                    if (fromUser) edit.setText(numToText(lo + progress * step))
                }
                override fun onStartTrackingTouch(s: SeekBar?) {}
                override fun onStopTrackingTouch(s: SeekBar?) {}
            })
            // 失焦时解析 + clamp（防呆），并同步滑块；单位文本不受影响
            edit.setOnFocusChangeListener { v, hasFocus ->
                if (!hasFocus) commitEdit()
            }
            set(clamp(toDouble(p.default) ?: lo))
        }

        fun clamp(v: Double): Double = v.coerceIn(lo, hi)

        fun commitEdit() {
            val v = toDouble(edit.text.toString().trim()) ?: toDouble(p.default) ?: lo
            set(clamp(v))
        }

        fun set(v: Double) {
            val cv = clamp(v)
            val rv = if (p.type == "int") cv.roundToInt().toDouble() else cv
            seek.progress = ((rv - lo) / step).roundToInt().coerceIn(0, seek.max)
            edit.setText(numToText(rv))
        }

        fun value(): Any {
            val v = toDouble(edit.text.toString().trim()) ?: toDouble(p.default) ?: lo
            val cv = clamp(v)
            return if (p.type == "int") cv.roundToInt() else cv
        }
    }

    init {
        orientation = VERTICAL
        setPadding(0, 8, 0, 8)
    }

    fun setParams(list: List<Param>) {
        removeAllViews()
        controls.clear()
        sliders.clear()
        params.clear()
        advToggle = null
        advContainer = null

        list.filter { it.tier == BASIC }.forEach { addRow(it, this) }

        val advanced = list.filter { it.tier != BASIC }
        if (advanced.isNotEmpty()) {
            advToggle = TextView(context).apply {
                text = context.getString(R.string.advanced_settings) + " ▸"
                textSize = 13f
                setPadding(0, dp(12), 0, dp(4))
                setTextColor(MaterialColors.getColor(
                    this, com.google.android.material.R.attr.colorPrimary))
                setOnClickListener { toggleAdvanced() }
            }
            addView(advToggle)
            advContainer = LinearLayout(context).apply {
                orientation = VERTICAL
                visibility = GONE
                setPadding(dp(8), 0, 0, 0)
            }
            advanced.forEach { addRow(it, advContainer!!) }
            addView(advContainer)
        }
        params += list
    }

    private fun toggleAdvanced() {
        val box = advContainer ?: return
        val show = box.visibility != VISIBLE
        box.visibility = if (show) VISIBLE else GONE
        advToggle?.text = context.getString(R.string.advanced_settings) +
            if (show) " ▾" else " ▸"
    }

    fun advancedVisible(): Boolean = advContainer?.visibility == VISIBLE

    private fun addRow(p: Param, parent: LinearLayout) {
        if ((p.type == "int" || p.type == "float") && p.min != null && p.max != null) {
            addSliderRow(p, parent)
        } else {
            addPlainRow(p, parent)
        }
    }

    // ---------------- 滑块行（有范围的数值参数） ----------------
    private fun addSliderRow(p: Param, parent: LinearLayout) {
        val col = LinearLayout(context).apply {
            orientation = VERTICAL
            setPadding(0, dp(6), 0, dp(6))
        }
        val label = TextView(context).apply {
            text = p.label
            textSize = 12f
            setTextColor(MaterialColors.getColor(
                this, com.google.android.material.R.attr.colorOnSurfaceVariant))
            if (p.help.isNotEmpty()) tooltipText = p.help
        }
        col.addView(label)

        val row = LinearLayout(context).apply {
            orientation = HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(0, dp(4), 0, 0)
        }
        val seek = SeekBar(context)
        val edit = EditText(context).apply {
            inputType = InputType.TYPE_CLASS_NUMBER or
                InputType.TYPE_NUMBER_FLAG_DECIMAL or InputType.TYPE_NUMBER_FLAG_SIGNED
            textSize = 13f
            applyCtrlStyle(this)
        }
        val unit = TextView(context).apply {
            text = p.unit
            textSize = 12f
            setTextColor(MaterialColors.getColor(
                this, com.google.android.material.R.attr.colorOnSurfaceVariant))
        }
        row.addView(seek, LayoutParams(0, dp(36), 1f))
        row.addView(edit, LayoutParams(dp(76), dp(44)).apply { marginStart = dp(8) })
        if (p.unit.isNotEmpty())
            row.addView(unit, LayoutParams(LayoutParams.WRAP_CONTENT,
                LayoutParams.WRAP_CONTENT).apply { marginStart = dp(6) })
        col.addView(row)

        parent.addView(col)
        sliders[p.key] = SliderRow(p, seek, edit)
    }

    // ---------------- 普通行 ----------------
    private fun addPlainRow(p: Param, parent: LinearLayout) {
        val row = LinearLayout(context)
        row.orientation = HORIZONTAL
        row.gravity = Gravity.CENTER_VERTICAL
        row.setPadding(0, 6, 0, 6)

        val label = TextView(context)
        label.text = p.label
        label.textSize = 12f
        label.width = dp(118)
        label.setTextColor(MaterialColors.getColor(
            this, com.google.android.material.R.attr.colorOnSurfaceVariant))
        if (p.help.isNotEmpty()) label.tooltipText = p.help
        row.addView(label)

        val ctrl = buildControl(p)
        val h = if (ctrl is EditText || ctrl is Spinner) dp(44)
                else LayoutParams.WRAP_CONTENT
        ctrl.layoutParams = LayoutParams(0, h, 1f)
        row.addView(ctrl)
        controls[p.key] = ctrl
        parent.addView(row)
    }

    private fun buildControl(p: Param): View = when (p.type) {
        "bool" -> CheckBox(context).apply {
            isChecked = p.default as? Boolean ?: false
            setTextColor(MaterialColors.getColor(
                this, com.google.android.material.R.attr.colorOnSurface))
        }
        "int", "float" -> styledNumberEdit(numToText(p.default))   // 无范围才走纯输入
        "choice" -> Spinner(context).apply {
            adapter = ArrayAdapter(context,
                android.R.layout.simple_spinner_item,
                p.choices.map { if (it.isEmpty()) context.getString(R.string.default_suffix) else it })
            val idx = p.choices.indexOf((p.default as? String) ?: "")
            setSelection(maxOf(0, idx))
            applyCtrlStyle(this)
        }
        else -> styledTextEdit((p.default as? String) ?: "").apply {
            if (p.unit.isNotEmpty()) hint = p.unit
        }
    }

    private fun styledNumberEdit(text: String): EditText = EditText(context).apply {
        inputType = InputType.TYPE_CLASS_NUMBER or
            InputType.TYPE_NUMBER_FLAG_DECIMAL or InputType.TYPE_NUMBER_FLAG_SIGNED
        setText(text)
        textSize = 13f
        applyCtrlStyle(this)
    }

    private fun styledTextEdit(text: String): EditText = EditText(context).apply {
        inputType = InputType.TYPE_CLASS_TEXT
        setText(text)
        textSize = 13f
        applyCtrlStyle(this)
    }

    /** 圆角填充背景 + 主题文字色 + 内边距，替代系统默认下划线输入框。 */
    private fun applyCtrlStyle(v: View) {
        v.background = ContextCompat.getDrawable(context, R.drawable.ctrl_card)
        v.setPadding(dp(12), 0, dp(12), 0)
        when (v) {
            is EditText -> v.setTextColor(MaterialColors.getColor(
                v, com.google.android.material.R.attr.colorOnSurface))
            is Spinner -> v.setPopupBackgroundDrawable(
                ContextCompat.getDrawable(context, R.drawable.row_card))
        }
    }

    private fun numToText(v: Any?): String = when (v) {
        null -> "0"
        is Double -> if (v == v.toLong().toDouble()) v.toLong().toString() else v.toString()
        is Int -> v.toString()
        else -> v.toString()
    }

    private fun toDouble(s: String?): Double? = s?.toDoubleOrNull()
    private fun toDouble(v: Any?): Double? = when (v) {
        is Number -> v.toDouble()
        is String -> v.toDoubleOrNull()
        else -> null
    }

    /** 取回所有参数值（滑块行自动 clamp 防呆）。 */
    fun values(): MutableMap<String, Any?> {
        val out = mutableMapOf<String, Any?>()
        for (p in params) {
            val sr = sliders[p.key]
            if (sr != null) { out[p.key] = sr.value(); continue }
            val c = controls[p.key] ?: continue
            out[p.key] = when (c) {
                is CheckBox -> c.isChecked
                is Spinner -> {
                    val pos = c.selectedItemPosition
                    if (pos in p.choices.indices) p.choices[pos] else ""
                }
                is EditText -> when (p.type) {
                    "int" -> c.text.toString().trim().toDoubleOrNull()?.toInt() ?: 0
                    "float" -> c.text.toString().trim().toDoubleOrNull() ?: 0.0
                    else -> c.text.toString().trim()
                }
                else -> null
            }
        }
        return out
    }

    fun setValues(values: Map<String, Any?>) {
        for (p in params) {
            val v = values[p.key] ?: continue
            val sr = sliders[p.key]
            if (sr != null) { toDouble(v)?.let { n -> sr.set(n) }; continue }
            when (val c = controls[p.key]) {
                is CheckBox -> c.isChecked = v as? Boolean ?: false
                is Spinner -> {
                    val idx = p.choices.indexOf(v.toString())
                    if (idx >= 0) c.setSelection(idx)
                }
                is EditText -> c.setText(
                    if (v is Double && v == v.toLong().toDouble()) v.toLong().toString()
                    else v.toString())
                else -> Unit
            }
        }
    }

    fun setEnabledAll(enabled: Boolean) {
        controls.values.forEach { it.isEnabled = enabled }
        sliders.values.forEach {
            it.seek.isEnabled = enabled
            it.edit.isEnabled = enabled
        }
        advToggle?.isEnabled = enabled
    }

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()
}
