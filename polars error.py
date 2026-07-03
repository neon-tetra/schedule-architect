import polars as pl

class Foo:
    pass
pl.show_versions()
foo_ids  = [1, 1, 1, 2, 3, 4, 4, 5]
foo_objs = [Foo() for _ in foo_ids]

df = pl.DataFrame({
    "foo_id":  foo_ids,
    "foo_obj": foo_objs
})

# does plain Object shift work (no list wrapping)?
df.sort("foo_id").with_columns(pl.col("foo_obj").shift(1))

# does shift work if you never go through group_by?
df.with_columns(pl.col("foo_obj").shift(1))

# (df.group_by("foo_id")
#    .agg(pl.col("foo_obj").alias("foo_obj_list"))
#    .with_columns(pl.col("foo_obj_list").shift(1).alias("foo_obj_list_shifted"))# Error
# )

"""
thread '<unnamed>' (9972) panicked at crates\polars-core\src\chunked_array\object\extension\drop.rs:19:9:
assertion failed: !ca.chunks.is_empty()
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace

thread '<unnamed>' (9972) panicked at crates\polars-core\src\chunked_array\object\extension\drop.rs:24:17:
assertion failed: matches!(dtype, ArrowDataType::Extension(_))
stack backtrace:
   0:     0x7ffb00174b92 - PyInit__polars_runtime
   1:     0x7ffaf7e34e11 - <unknown>
   2:     0x7ffb00173cd4 - PyInit__polars_runtime
   3:     0x7ffb001740a9 - PyInit__polars_runtime
   4:     0x7ffaf9a50898 - ffi_select_with_compiled_path
   5:     0x7ffb00173aea - PyInit__polars_runtime
   6:     0x7ffb0017b00a - PyInit__polars_runtime
   7:     0x7ffb0017af6f - PyInit__polars_runtime
   8:     0x7ffb0017c60e - PyInit__polars_runtime
   9:     0x7ffb002dbfed - PyInit__polars_runtime
  10:     0x7ffb002dc187 - PyInit__polars_runtime
  11:     0x7ffaf86d06f4 - ffi_select_with_compiled_path
  12:     0x7ffaf86e1433 - ffi_select_with_compiled_path
  13:     0x7ffaf94c9b21 - ffi_select_with_compiled_path
  14:     0x7ffbbb451060 - <unknown>
  15:     0x7ffbbb4553ea - is_exception_typeof
  16:     0x7ffbbb45fb50 - _C_specific_handler
  17:     0x7ffbbb4545f0 - is_exception_typeof
  18:     0x7ffbbb460481 - _CxxFrameHandler3
  19:     0x7ffbee0c481f - _chkstk
  20:     0x7ffbedfa2103 - RtlUnwindEx
  21:     0x7ffbbb460016 - _C_specific_handler
  22:     0x7ffbbb453245 - is_exception_typeof
  23:     0x7ffbbb453666 - is_exception_typeof
  24:     0x7ffbbb4546ec - is_exception_typeof
  25:     0x7ffbbb460481 - _CxxFrameHandler3
  26:     0x7ffbee0c479f - _chkstk
  27:     0x7ffbedfa5e97 - RtlLocateExtendedFeature
  28:     0x7ffbedfed011 - RtlRaiseException
  29:     0x7ffbeb7a1c0a - RaiseException
  30:     0x7ffbbb456ba7 - CxxThrowException
  31:     0x7ffaf81444fd - ffi_select_with_compiled_path
  32:     0x7ffaf8144474 - ffi_select_with_compiled_path
  33:     0x7ffb0017414f - PyInit__polars_runtime
  34:     0x7ffb00173b08 - PyInit__polars_runtime
  35:     0x7ffb0017b00a - PyInit__polars_runtime
  36:     0x7ffb0017af6f - PyInit__polars_runtime
  37:     0x7ffb0017c60e - PyInit__polars_runtime
  38:     0x7ffb002dbfed - PyInit__polars_runtime
  39:     0x7ffb002dc187 - PyInit__polars_runtime
  40:     0x7ffaf86d075e - ffi_select_with_compiled_path
  41:     0x7ffaf94ca897 - ffi_select_with_compiled_path
  42:     0x7ffaf94c97c7 - ffi_select_with_compiled_path
  43:     0x7ffaf94c9304 - ffi_select_with_compiled_path
  44:     0x7ffafa1aba7e - ffi_select_with_compiled_path
  45:     0x7ffafa4bc37a - ffi_select_with_compiled_path
  46:     0x7ffafa4bb805 - ffi_select_with_compiled_path
  47:     0x7ffaf9b349c5 - ffi_select_with_compiled_path
  48:     0x7ffafaafc0d3 - ffi_select_with_compiled_path
  49:     0x7ffafaafa977 - ffi_select_with_compiled_path
  50:     0x7ffafaaf95ac - ffi_select_with_compiled_path
  51:     0x7ffafaaf0c12 - ffi_select_with_compiled_path
  52:     0x7ffafaa20aaf - ffi_select_with_compiled_path
  53:     0x7ffafeb1e6c4 - ffi_select_with_compiled_path
  54:     0x7ffafd5a8f1c - ffi_select_with_compiled_path
  55:     0x7ffafeacdd64 - ffi_select_with_compiled_path
  56:     0x7ffb2ebd4ad6 - PyArg_ParseStackAndKeywords
  57:     0x7ffb2eb5c13b - PyObject_Vectorcall
  58:     0x7ffb2eb5d423 - PyEval_EvalFrameDefault
  59:     0x7ffb2eb5ae64 - PyFunction_Vectorcall
  60:     0x7ffb2ec04c6a - PyObject_CallObject
  61:     0x7ffb2eb61f7f - PyEval_EvalFrameDefault
  62:     0x7ffb2eb5ae64 - PyFunction_Vectorcall
  63:     0x7ffb2ec04c6a - PyObject_CallObject
  64:     0x7ffb2eb61f7f - PyEval_EvalFrameDefault
  65:     0x7ffb2eb37feb - PyType_CalculateMetaclass
  66:     0x7ffb2ec02533 - PyEval_EvalCode
  67:     0x7ffb2ec027ca - PyEval_EvalCode
  68:     0x7ffb2ec02746 - PyEval_EvalCode
  69:     0x7ffb2ecfed26 - PyThread_tss_is_created
  70:     0x7ffb2ec6f0c9 - PyRun_SimpleFileObject
  71:     0x7ffb2ec6ee38 - PyRun_AnyFileObject
  72:     0x7ffb2ec6ea87 - PyDict_Values
  73:     0x7ffb2ec6e943 - PyDict_Values
  74:     0x7ffb2eb2a4ec - Py_RunMain
  75:     0x7ffb2eb2a37d - Py_RunMain
  76:     0x7ff6641342fb - <unknown>
  77:     0x7ff6641358b4 - <unknown>
  78:     0x7ffbec9ae957 - BaseThreadInitThunk
  79:     0x7ffbee00ad6c - RtlUserThreadStart
"""