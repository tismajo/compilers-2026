# Define your site below.
# Run the compiler and it will generate HTML, create a GitHub repo, and deploy to Vercel.

site "my-portfolio-compilers" {
  title       = "María José Girón Isidro, Leonardo Dufrey Mejía Mejía, Milton Giovanni Palanco Serrano — UVG 2026"
  description = "Estudiantes de CS construyendo compiladores"
  theme       = "dark"

  page "index" {
    hero    = "¿Por qué fue la computadora al dentista? Para que le revisaran el Bluetooth."
    about   = "Somos unos estudiantes de Ciencia de computación en la UVG. Esta página se ha generado a partir de un DSL personalizado, se ha subido a GitHub y se ha implementado en Vercel, todo ello gracias a mi compilador ANTLR."
    contact = "gir23559@uvg.edu.gt, mej23648@uvg.edu.gt, pol471@uvg.edu.gt"
  }
}
