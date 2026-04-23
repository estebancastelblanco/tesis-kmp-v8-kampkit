package co.touchlab.kampkit.db

import app.cash.sqldelight.Transacter
import app.cash.sqldelight.db.QueryResult
import app.cash.sqldelight.db.SqlDriver
import app.cash.sqldelight.db.SqlSchema
import co.touchlab.kampkit.db.shared.newInstance
import co.touchlab.kampkit.db.shared.schema
import kotlin.Unit

public interface KaMPKitDb : Transacter {
  public val tableQueries: TableQueries

  public companion object {
    public val Schema: SqlSchema<QueryResult.Value<Unit>>
      get() = KaMPKitDb::class.schema

    public operator fun invoke(driver: SqlDriver): KaMPKitDb = KaMPKitDb::class.newInstance(driver)
  }
}
