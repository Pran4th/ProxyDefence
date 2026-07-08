if [ ! -f "$1/.env" ]; then
    echo "ERROR: .env not found at $1/.env" >&2
    return 1
fi

while IFS= read -r line || [ -n "$line" ]; do
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    case "$line" in
        ''|'#'*) continue ;;
    esac
    key="${line%%=*}"
    val="${line#*=}"
    val="${val#\"}"
    val="${val%\"}"
    val="${val#\'}"
    val="${val%\'}"
    export "$key=$val"
done < "$1/.env"
