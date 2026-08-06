package cn.mediaforge.app

import android.content.Context
import android.text.InputType
import android.view.View
import android.widget.ArrayAdapter
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.Spinner
import android.widget.TextView

/** 依据 Formats.Param 目录自动生成参数编辑控件（桌面版 widgets.ParamForm 的移植）。 */
class ParamForm @JvmOverloads constructor(
    context: Context, attrs: android.util.AttributeSet? = null,
) : LinearLayout(context, attrs) {

    private val controls = LinkedHashMap<String, View>()
    private val params = mutableListOf<Param>()

    init {
        orientation = VERTICAL
        setPadding(0, 8, 0, 8)
    }

    fun setParams(list: List<Param>) {
        removeAllViews()
        controls.clear()
        params.clear()
        for (p in list) {
            val row = LinearLayout(context)
            row.orientation = HORIZONTAL
            row.setPadding(0, 4, 0, 4)

            val label = TextView(context)
            label.text = p.label
            label.textSize = 12f
            label.width = dp(118)
            if (p.help.isNotEmpty()) label.tooltipText = p.help
            row.addView(label)

            val ctrl = buildControl(p)
            ctrl.layoutParams = LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f)
            row.addView(ctrl)
            controls[p.key] = ctrl
            params += p
            addView(row)
        }
    }

    private fun buildControl(p: Param): View = when (p.type) {
        "bool" -> CheckBox(context).apply { isChecked = p.default as? Boolean ?: false }
        "int", "float" -> EditText(context).apply {
            inputType = InputType.TYPE_CLASS_NUMBER or
                InputType.TYPE_NUMBER_FLAG_DECIMAL or InputType.TYPE_NUMBER_FLAG_SIGNED
            setText(numToText(p.default))
            textSize = 13f
        }
        "choice" -> Spinner(context).apply {
            adapter = ArrayAdapter(context,
                android.R.layout.simple_spinner_item,
                p.choices.map { if (it.isEmpty()) context.getString(R.string.default_suffix) else it })
            val idx = p.choices.indexOf((p.default as? String) ?: "")
            setSelection(maxOf(0, idx))
        }
        else -> EditText(context).apply {
            inputType = InputType.TYPE_CLASS_TEXT
            setText((p.default as? String) ?: "")
            textSize = 13f
        }
    }

    private fun numToText(v: Any?): String = when (v) {
        null -> "0"
        is Double -> if (v == v.toLong().toDouble()) v.toLong().toString() else v.toString()
        else -> v.toString()
    }

    /** 取回所有参数值。 */
    fun values(): MutableMap<String, Any?> {
        val out = mutableMapOf<String, Any?>()
        for (p in params) {
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
    }

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()
}
