package com.example.di

import com.example.common.ExpenseRepoImpl
import com.example.ui.ExpensesViewModel

fun appModule() {
    val repo = ExpenseRepoImpl()
    val vm = ExpensesViewModel(repo)
}
