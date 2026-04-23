package co.touchlab.kampkit.db

import app.cash.sqldelight.Query
import app.cash.sqldelight.TransacterImpl
import app.cash.sqldelight.db.QueryResult
import app.cash.sqldelight.db.SqlCursor
import app.cash.sqldelight.db.SqlDriver
import kotlin.Any
import kotlin.Boolean
import kotlin.Long
import kotlin.String

public class TableQueries(
  driver: SqlDriver,
) : TransacterImpl(driver) {
  public fun <T : Any> selectAll(mapper: (
    id: Long,
    name: String,
    favorite: Boolean,
  ) -> T): Query<T> = Query(787_999_478, arrayOf("Breed"), driver, "Table.sq", "selectAll", "SELECT Breed.id, Breed.name, Breed.favorite FROM Breed") { cursor ->
    mapper(
      cursor.getLong(0)!!,
      cursor.getString(1)!!,
      cursor.getBoolean(2)!!
    )
  }

  public fun selectAll(): Query<Breed> = selectAll(::Breed)

  public fun <T : Any> selectById(id: Long, mapper: (
    id: Long,
    name: String,
    favorite: Boolean,
  ) -> T): Query<T> = SelectByIdQuery(id) { cursor ->
    mapper(
      cursor.getLong(0)!!,
      cursor.getString(1)!!,
      cursor.getBoolean(2)!!
    )
  }

  public fun selectById(id: Long): Query<Breed> = selectById(id, ::Breed)

  public fun <T : Any> selectByName(name: String, mapper: (
    id: Long,
    name: String,
    favorite: Boolean,
  ) -> T): Query<T> = SelectByNameQuery(name) { cursor ->
    mapper(
      cursor.getLong(0)!!,
      cursor.getString(1)!!,
      cursor.getBoolean(2)!!
    )
  }

  public fun selectByName(name: String): Query<Breed> = selectByName(name, ::Breed)

  /**
   * @return The number of rows updated.
   */
  public fun insertBreed(name: String): QueryResult<Long> {
    val result = driver.execute(1_035_749_868, """
        |INSERT OR IGNORE INTO Breed(name)
        |VALUES (?)
        """.trimMargin(), 1) {
          var parameterIndex = 0
          bindString(parameterIndex++, name)
        }
    notifyQueries(1_035_749_868) { emit ->
      emit("Breed")
    }
    return result
  }

  /**
   * @return The number of rows updated.
   */
  public fun deleteAll(): QueryResult<Long> {
    val result = driver.execute(2_145_265_639, """DELETE FROM Breed""", 0)
    notifyQueries(2_145_265_639) { emit ->
      emit("Breed")
    }
    return result
  }

  /**
   * @return The number of rows updated.
   */
  public fun updateFavorite(favorite: Boolean, id: Long): QueryResult<Long> {
    val result = driver.execute(1_496_370_228, """UPDATE Breed SET favorite = ? WHERE id = ?""", 2) {
          var parameterIndex = 0
          bindBoolean(parameterIndex++, favorite)
          bindLong(parameterIndex++, id)
        }
    notifyQueries(1_496_370_228) { emit ->
      emit("Breed")
    }
    return result
  }

  private inner class SelectByIdQuery<out T : Any>(
    public val id: Long,
    mapper: (SqlCursor) -> T,
  ) : Query<T>(mapper) {
    override fun addListener(listener: Query.Listener) {
      driver.addListener("Breed", listener = listener)
    }

    override fun removeListener(listener: Query.Listener) {
      driver.removeListener("Breed", listener = listener)
    }

    override fun <R> execute(mapper: (SqlCursor) -> QueryResult<R>): QueryResult<R> = driver.executeQuery(-1_341_778_659, """SELECT Breed.id, Breed.name, Breed.favorite FROM Breed WHERE id = ?""", mapper, 1) {
      var parameterIndex = 0
      bindLong(parameterIndex++, id)
    }

    override fun toString(): String = "Table.sq:selectById"
  }

  private inner class SelectByNameQuery<out T : Any>(
    public val name: String,
    mapper: (SqlCursor) -> T,
  ) : Query<T>(mapper) {
    override fun addListener(listener: Query.Listener) {
      driver.addListener("Breed", listener = listener)
    }

    override fun removeListener(listener: Query.Listener) {
      driver.removeListener("Breed", listener = listener)
    }

    override fun <R> execute(mapper: (SqlCursor) -> QueryResult<R>): QueryResult<R> = driver.executeQuery(-958_952_947, """SELECT Breed.id, Breed.name, Breed.favorite FROM Breed WHERE name = ?""", mapper, 1) {
      var parameterIndex = 0
      bindString(parameterIndex++, name)
    }

    override fun toString(): String = "Table.sq:selectByName"
  }
}
